#!/usr/bin/env bash
set -euo pipefail

# Fails fast when registration->product anchor gap is too large.
# Default threshold is 5% unanchored registrations.
MAX_RATIO="${MAX_RATIO:-0.05}"
MAX_UNANCHORED_COUNT="${MAX_UNANCHORED_COUNT:-0}"
DB_USER="${DB_USER:-nmpa}"
DB_NAME="${DB_NAME:-nmpa}"

metrics_sql=$(
  cat <<'SQL'
WITH stats AS (
  SELECT
    COUNT(*)::bigint AS total_regs,
    COUNT(*) FILTER (
      WHERE NOT EXISTS (
        SELECT 1 FROM products p WHERE p.registration_id = r.id
      )
    )::bigint AS unanchored_regs
  FROM registrations r
)
SELECT total_regs, unanchored_regs FROM stats;
SQL
)

read -r total unanchored <<<"$(
  docker compose exec -T db psql -U "${DB_USER}" -d "${DB_NAME}" -At -F ' ' -c "${metrics_sql}" \
    | tail -n 1
)"

if [[ -z "${total:-}" || -z "${unanchored:-}" ]]; then
  echo "[anchor-gate] unable to read metrics"
  exit 2
fi

ratio="$(awk -v t="${total}" -v u="${unanchored}" 'BEGIN{ if (t==0) {print "0.000000"} else {printf "%.6f", u/t} }')"
pass_ratio="$(awk -v r="${ratio}" -v m="${MAX_RATIO}" 'BEGIN{ if (r<=m) print 1; else print 0 }')"
pass_count=1
if [[ "${MAX_UNANCHORED_COUNT}" -gt 0 ]]; then
  pass_count="$(awk -v u="${unanchored}" -v m="${MAX_UNANCHORED_COUNT}" 'BEGIN{ if (u<=m) print 1; else print 0 }')"
fi

echo "[anchor-gate] total=${total} unanchored=${unanchored} ratio=${ratio} max_ratio=${MAX_RATIO} max_count=${MAX_UNANCHORED_COUNT}"

if [[ "${pass_ratio}" != "1" || "${pass_count}" != "1" ]]; then
  echo "[anchor-gate] FAILED"
  exit 1
fi

echo "[anchor-gate] PASSED"

