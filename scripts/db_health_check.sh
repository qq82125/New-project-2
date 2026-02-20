#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

POSTGRES_USER="${POSTGRES_USER:-nmpa}"
POSTGRES_DB="${POSTGRES_DB:-nmpa}"
SQL_FILE="${ROOT_DIR}/scripts/sql/db_health_checks.sql"

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "[db-health][ERROR] sql file not found: ${SQL_FILE}"
  exit 1
fi

echo "[db-health] running 5 checks on db=${POSTGRES_DB}"
docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -f /dev/stdin < "${SQL_FILE}"
echo "[db-health] done"
