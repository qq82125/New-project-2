#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

POSTGRES_USER="${POSTGRES_USER:-nmpa}"
POSTGRES_DB="${POSTGRES_DB:-nmpa}"
DRILL_DB_PREFIX="${DRILL_DB_PREFIX:-restore_drill}"
BASE_DIR="${ROOT_DIR}/backups/postgres/base"
CHECK_TABLES="${CHECK_TABLES:-registrations products source_runs}"
STRICT="${STRICT:-0}"

latest_base="$(find "${BASE_DIR}" -mindepth 1 -maxdepth 1 -type f -name 'base_*.dump' | sort | tail -n 1 || true)"
if [[ -z "${latest_base}" ]]; then
  echo "[restore-drill][ERROR] no base backup found under ${BASE_DIR}"
  exit 1
fi

stamp="$(date +%Y%m%d_%H%M%S)"
drill_db="${DRILL_DB_PREFIX}_${stamp}"

echo "[restore-drill] source dump: ${latest_base}"
echo "[restore-drill] create drill db: ${drill_db}"
docker compose exec -T db psql -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${drill_db};"

cleanup() {
  echo "[restore-drill] drop drill db: ${drill_db}"
  docker compose exec -T db psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${drill_db};" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[restore-drill] restoring dump"
cat "${latest_base}" | docker compose exec -T db pg_restore -U "${POSTGRES_USER}" -d "${drill_db}" --no-owner --no-privileges >/dev/null

echo "[restore-drill] validating required tables"
for t in ${CHECK_TABLES}; do
  cnt="$(
    docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${drill_db}" -At -v ON_ERROR_STOP=1 \
      -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='${t}';" \
      | tr -d '[:space:]'
  )"
  if [[ "${cnt}" != "1" ]]; then
    echo "[restore-drill][ERROR] missing table in restored db: ${t}"
    exit 1
  fi
done

echo "[restore-drill] row count snapshot"
docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${drill_db}" -v ON_ERROR_STOP=1 -c \
  "SELECT 'registrations' AS table_name, count(*) AS rows FROM registrations
   UNION ALL SELECT 'products', count(*) FROM products
   UNION ALL SELECT 'source_runs', count(*) FROM source_runs;"

if [[ "${STRICT}" == "1" ]]; then
  echo "[restore-drill] strict comparison against primary db"
  live_counts="$(
    docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -F $'\t' -v ON_ERROR_STOP=1 -c \
      "SELECT (SELECT count(*) FROM registrations), (SELECT count(*) FROM products), (SELECT count(*) FROM source_runs);" \
      | tail -n 1
  )"
  drill_counts="$(
    docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${drill_db}" -At -F $'\t' -v ON_ERROR_STOP=1 -c \
      "SELECT (SELECT count(*) FROM registrations), (SELECT count(*) FROM products), (SELECT count(*) FROM source_runs);" \
      | tail -n 1
  )"
  if [[ "${live_counts}" != "${drill_counts}" ]]; then
    echo "[restore-drill][ERROR] strict row-count mismatch live=${live_counts} restored=${drill_counts}"
    exit 1
  fi
fi

echo "[restore-drill] PASS"
