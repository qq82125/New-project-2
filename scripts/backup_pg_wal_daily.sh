#!/usr/bin/env bash
set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-nmpa}"
PGDATABASE="${PGDATABASE:-nmpa}"
WAL_ARCHIVE_DIR="${WAL_ARCHIVE_DIR:-/wal}"
WAL_RETENTION_DAYS="${WAL_RETENTION_DAYS:-14}"

mkdir -p "${WAL_ARCHIVE_DIR}"

echo "[wal-daily] force wal switch + checkpoint"
psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname="${PGDATABASE}" -At -c "SELECT pg_switch_wal();"
psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname="${PGDATABASE}" -c "CHECKPOINT;"

find "${WAL_ARCHIVE_DIR}" -type f -name "*.backup" -mtime +"${WAL_RETENTION_DAYS}" -delete || true
find "${WAL_ARCHIVE_DIR}" -type f -regex ".*[0-9A-F]\{24\}$" -mtime +"${WAL_RETENTION_DAYS}" -delete || true

wal_count="$(find "${WAL_ARCHIVE_DIR}" -type f | wc -l | tr -d '[:space:]')"
echo "[wal-daily] archived_files=${wal_count}"

