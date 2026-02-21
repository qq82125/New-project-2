#!/usr/bin/env bash
set -euo pipefail

BATCH_SIZE="${BATCH_SIZE:-2000}"
MAX_BATCHES="${MAX_BATCHES:-80}"

run_batch() {
  cat <<SQL | docker compose exec -T -e PGOPTIONS="-c statement_timeout=25s" db psql -U nmpa -d nmpa -At
WITH target AS (
  SELECT r.id AS reg_id, r.registration_no, COALESCE(NULLIF(BTRIM(r.status),''), 'UNKNOWN') AS reg_status
  FROM registrations r
  WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.registration_id = r.id)
    AND EXISTS (SELECT 1 FROM product_variants v WHERE v.registration_id = r.id)
  ORDER BY r.created_at ASC, r.id ASC
  LIMIT ${BATCH_SIZE}
),
latest AS (
  SELECT t.reg_id, t.registration_no, t.reg_status, lv.product_name, lv.model_spec, lv.ivd_category
  FROM target t
  JOIN LATERAL (
    SELECT v.product_name, v.model_spec, v.ivd_category
    FROM product_variants v
    WHERE v.registration_id = t.reg_id
    ORDER BY v.updated_at DESC NULLS LAST, v.created_at DESC NULLS LAST, v.id ASC
    LIMIT 1
  ) lv ON TRUE
),
upserted AS (
  INSERT INTO products (udi_di, reg_no, name, status, is_ivd, ivd_category, registration_id, raw_json, raw, ivd_source, ivd_confidence)
  SELECT
    'reg:' || l.registration_no,
    l.registration_no,
    LEFT(COALESCE(NULLIF(BTRIM(l.product_name),''), NULLIF(BTRIM(l.model_spec),''), l.registration_no), 500),
    l.reg_status,
    TRUE,
    COALESCE(NULLIF(BTRIM(l.ivd_category),''), 'unknown'),
    l.reg_id,
    jsonb_build_object('_stub', jsonb_build_object('source_hint','BACKFILL','verified_by_nmpa',false,'evidence_level','LOW')),
    '{}'::jsonb,
    'BACKFILL',
    0.40
  FROM latest l
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

for i in $(seq 1 "${MAX_BATCHES}"); do
  n="$(run_batch | tr -d '[:space:]')"
  echo "batch_${i}=${n}"
  if [[ "${n}" == "0" ]]; then
    break
  fi
  sleep 0.2
done
