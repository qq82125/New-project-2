#!/usr/bin/env bash
set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-nmpa}"
PGDATABASE="${PGDATABASE:-nmpa}"
BACKUP_DIR="${BACKUP_DIR:-/backup}"
FULL_BACKUP_RETENTION_WEEKS="${FULL_BACKUP_RETENTION_WEEKS:-4}"
FULL_BACKUP_MAX_RATE="${FULL_BACKUP_MAX_RATE:-80M}"
STAMP="$(date +%F_%H%M%S)"
TARGET_DIR="${BACKUP_DIR}/base/base_${STAMP}"

mkdir -p "${BACKUP_DIR}/base"

echo "[full-backup] start ${TARGET_DIR}"
pg_basebackup \
  --host="${PGHOST}" \
  --port="${PGPORT}" \
  --username="${PGUSER}" \
  --pgdata="${TARGET_DIR}" \
  --format=tar \
  --gzip \
  --wal-method=stream \
  --checkpoint=fast \
  --max-rate="${FULL_BACKUP_MAX_RATE}" \
  --label="weekly_base_${STAMP}"

retention_days="$(( FULL_BACKUP_RETENTION_WEEKS * 7 ))"
find "${BACKUP_DIR}/base" -mindepth 1 -maxdepth 1 -type d -name "base_*" -mtime +"${retention_days}" -exec rm -rf {} +
echo "[full-backup] done"

