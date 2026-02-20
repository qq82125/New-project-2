#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

POSTGRES_USER="${POSTGRES_USER:-nmpa}"
POSTGRES_DB="${POSTGRES_DB:-nmpa}"
EXPECTED_DATA_MOUNT_HINT="${EXPECTED_DATA_MOUNT_HINT:-.local/pgdata}"
PRECHECK_REQUIRE_BASE_BACKUP="${PRECHECK_REQUIRE_BASE_BACKUP:-1}"
PRECHECK_REQUIRE_WAL="${PRECHECK_REQUIRE_WAL:-1}"
PRECHECK_MAX_BASE_AGE_DAYS="${PRECHECK_MAX_BASE_AGE_DAYS:-8}"

BACKUP_ROOT="${ROOT_DIR}/backups/postgres"
BASE_DIR="${BACKUP_ROOT}/base"
WAL_DIR="${BACKUP_ROOT}/wal"

errors=0
warns=0

say() {
  echo "[preflight] $*"
}

warn() {
  warns=$((warns + 1))
  echo "[preflight][WARN] $*"
}

fail() {
  errors=$((errors + 1))
  echo "[preflight][ERROR] $*"
}

mtime_epoch() {
  local target="$1"
  if stat -f %m "${target}" >/dev/null 2>&1; then
    stat -f %m "${target}"
  else
    stat -c %Y "${target}"
  fi
}

say "checking docker compose DB data mount"
compose_cfg="$(docker compose config)"
if ! echo "${compose_cfg}" | grep -q '/var/lib/postgresql/data'; then
  fail "cannot find db data mount in compose config"
else
  mount_lines="$(echo "${compose_cfg}" | grep -E '(/var/lib/postgresql/data|\.local/pgdata)' || true)"
  say "db mount lines: ${mount_lines}"
  if ! echo "${compose_cfg}" | grep -q "${EXPECTED_DATA_MOUNT_HINT}"; then
    fail "db mount does not contain expected hint '${EXPECTED_DATA_MOUNT_HINT}'"
  fi
fi

say "checking db connectivity"
if ! docker compose exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
  fail "database is not ready"
else
  say "database is ready"
fi

say "checking key table existence"
table_info="$(
  docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -F $'\t' -c \
    "SELECT coalesce(to_regclass('public.registrations')::text,''), coalesce(to_regclass('public.products')::text,''), coalesce(to_regclass('public.source_runs')::text,'');" \
    | tail -n 1
)"
reg_table="$(echo "${table_info}" | awk -F $'\t' '{print $1}')"
prod_table="$(echo "${table_info}" | awk -F $'\t' '{print $2}')"
run_table="$(echo "${table_info}" | awk -F $'\t' '{print $3}')"
if [[ -z "${reg_table}" || -z "${prod_table}" || -z "${run_table}" ]]; then
  fail "required tables missing (registrations/products/source_runs)"
fi

say "checking key table counts"
counts="$(
  docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -F $'\t' -c \
    "SELECT (SELECT count(*) FROM registrations), (SELECT count(*) FROM products), (SELECT count(*) FROM source_runs), (SELECT count(*) FROM daily_metrics);" \
    | tail -n 1
)"
reg_count="$(echo "${counts}" | awk -F $'\t' '{print $1}')"
prod_count="$(echo "${counts}" | awk -F $'\t' '{print $2}')"
run_count="$(echo "${counts}" | awk -F $'\t' '{print $3}')"
metrics_count="$(echo "${counts}" | awk -F $'\t' '{print $4}')"
say "counts registrations=${reg_count} products=${prod_count} source_runs=${run_count} daily_metrics=${metrics_count}"

if [[ "${run_count}" -gt 0 && "${reg_count}" -eq 0 ]]; then
  fail "source_runs>0 but registrations=0 (possible wrong db mount or data loss)"
fi
if [[ "${reg_count}" -gt 0 && "${prod_count}" -eq 0 ]]; then
  fail "registrations>0 but products=0 (ingest chain may be broken)"
fi
if [[ "${metrics_count}" -eq 0 ]]; then
  warn "daily_metrics is empty"
fi

say "checking backup availability"
mkdir -p "${BASE_DIR}" "${WAL_DIR}"
latest_base="$(find "${BASE_DIR}" -mindepth 1 -maxdepth 1 -type f -name 'base_*.dump' | sort | tail -n 1 || true)"
wal_count="$(find "${WAL_DIR}" -type f | wc -l | tr -d '[:space:]')"

if [[ -z "${latest_base}" ]]; then
  if [[ "${PRECHECK_REQUIRE_BASE_BACKUP}" == "1" ]]; then
    fail "no base backup found under ${BASE_DIR}"
  else
    warn "no base backup found under ${BASE_DIR}"
  fi
else
  now_epoch="$(date +%s)"
  base_epoch="$(mtime_epoch "${latest_base}")"
  age_days="$(( (now_epoch - base_epoch) / 86400 ))"
  say "latest base backup=${latest_base} age_days=${age_days}"
  if [[ "${age_days}" -gt "${PRECHECK_MAX_BASE_AGE_DAYS}" ]]; then
    fail "base backup is too old (${age_days} days > ${PRECHECK_MAX_BASE_AGE_DAYS} days)"
  fi
fi

if [[ "${wal_count}" -eq 0 ]]; then
  if [[ "${PRECHECK_REQUIRE_WAL}" == "1" ]]; then
    fail "no wal archive files found under ${WAL_DIR}"
  else
    warn "no wal archive files found under ${WAL_DIR}"
  fi
else
  say "wal archive files=${wal_count}"
fi

if [[ "${errors}" -gt 0 ]]; then
  echo "[preflight] FAILED errors=${errors} warnings=${warns}"
  exit 1
fi

echo "[preflight] PASSED warnings=${warns}"
