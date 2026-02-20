#!/usr/bin/env bash
set -euo pipefail

# Safe mode by default: preview only. Set APPLY=1 to execute writes.
APPLY="${APPLY:-0}"
BATCH_SIZE="${BATCH_SIZE:-200}"
MAX_BATCHES="${MAX_BATCHES:-20}"

if [[ "${APPLY}" != "0" && "${APPLY}" != "1" ]]; then
  echo "APPLY must be 0 or 1"
  exit 1
fi

preview_sql() {
  cat <<'SQL'
SET statement_timeout='20s';
WITH remaining AS (
  SELECT r.id, r.registration_no
  FROM registrations r
  WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.registration_id = r.id)
)
SELECT
  COUNT(*) AS remaining_total,
  COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM product_variants v WHERE v.registration_id = remaining.id)) AS with_variants,
  COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM product_variants v WHERE v.registration_id = remaining.id)) AS without_variants
FROM remaining;
SQL
}

batch_sql() {
  cat <<SQL
SET statement_timeout='25s';
WITH target AS (
  SELECT
    r.id AS reg_id,
    r.registration_no,
    COALESCE(NULLIF(BTRIM(r.status), ''), 'UNKNOWN') AS reg_status,
    COALESCE(
      NULLIF(BTRIM(r.raw_json->'_latest_payload'->>'product_name'), ''),
      NULLIF(BTRIM(r.raw_json->'_latest_payload'->>'name'), ''),
      NULLIF(BTRIM(r.raw_json->'_latest_payload'->>'产品名称'), ''),
      NULLIF(BTRIM(r.raw_json->'_latest_payload'->>'产品名'), '')
    ) AS reg_payload_name
  FROM registrations r
  WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.registration_id = r.id)
  ORDER BY r.created_at ASC, r.id ASC
  LIMIT ${BATCH_SIZE}
),
name_from_map AS (
  SELECT
    t.reg_id,
    COALESCE(
      NULLIF(BTRIM(rsr.payload->>'product_name'), ''),
      NULLIF(BTRIM(rsr.payload->>'name'), ''),
      NULLIF(BTRIM(rsr.payload->>'catalog_item_std'), ''),
      NULLIF(BTRIM(rsr.payload->>'catalog_item_raw'), '')
    ) AS map_name
  FROM target t
  LEFT JOIN LATERAL (
    SELECT m.raw_source_record_id
    FROM product_udi_map m
    WHERE m.registration_no = t.registration_no
    ORDER BY m.updated_at DESC NULLS LAST, m.created_at DESC NULLS LAST
    LIMIT 1
  ) mr ON TRUE
  LEFT JOIN raw_source_records rsr ON rsr.id = mr.raw_source_record_id
),
final_rows AS (
  SELECT
    t.reg_id,
    t.registration_no,
    t.reg_status,
    LEFT(COALESCE(nm.map_name, t.reg_payload_name, t.registration_no), 500) AS anchor_name
  FROM target t
  LEFT JOIN name_from_map nm ON nm.reg_id = t.reg_id
),
upserted AS (
  INSERT INTO products (
    udi_di,
    reg_no,
    name,
    status,
    is_ivd,
    ivd_category,
    registration_id,
    raw_json,
    raw,
    ivd_source,
    ivd_confidence
  )
  SELECT
    'reg:' || f.registration_no,
    f.registration_no,
    f.anchor_name,
    f.reg_status,
    TRUE,
    'unknown',
    f.reg_id,
    jsonb_build_object(
      '_stub', jsonb_build_object(
        'source_hint', 'BACKFILL_REMAINING',
        'verified_by_nmpa', false,
        'evidence_level', 'LOW'
      )
    ),
    '{}'::jsonb,
    'BACKFILL_REMAINING',
    0.30
  FROM final_rows f
  ON CONFLICT (udi_di) DO UPDATE SET
    reg_no = EXCLUDED.reg_no,
    registration_id = COALESCE(products.registration_id, EXCLUDED.registration_id),
    name = COALESCE(NULLIF(products.name, ''), EXCLUDED.name),
    status = COALESCE(NULLIF(products.status, ''), EXCLUDED.status),
    is_ivd = COALESCE(products.is_ivd, EXCLUDED.is_ivd),
    ivd_category = COALESCE(NULLIF(products.ivd_category, ''), EXCLUDED.ivd_category),
    ivd_source = COALESCE(products.ivd_source, EXCLUDED.ivd_source),
    ivd_confidence = COALESCE(products.ivd_confidence, EXCLUDED.ivd_confidence),
    updated_at = NOW()
  RETURNING 1
)
SELECT COUNT(*) FROM upserted;
SQL
}

remaining_sql() {
  cat <<'SQL'
SET statement_timeout='20s';
SELECT COUNT(*)
FROM registrations r
WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.registration_id = r.id);
SQL
}

echo "[preview] current remaining-unanchored breakdown:"
preview_sql | docker compose exec -T db psql -U nmpa -d nmpa

if [[ "${APPLY}" == "0" ]]; then
  echo "[dry-run] APPLY=0, no writes executed."
  exit 0
fi

for i in $(seq 1 "${MAX_BATCHES}"); do
  n="$(
    batch_sql \
      | docker compose exec -T -e PGOPTIONS="-c statement_timeout=25s" db psql -U nmpa -d nmpa -At \
      | tr -d '[:space:]'
  )"
  echo "batch_${i}=${n}"
  if [[ "${n}" == "0" ]]; then
    break
  fi
  sleep 0.2
done

left="$(
  remaining_sql \
    | docker compose exec -T db psql -U nmpa -d nmpa -At \
    | tail -n 1 \
    | tr -d '[:space:]'
)"
echo "remaining_after=${left}"
