#!/usr/bin/env bash
set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-nmpa}"
PGDATABASE="${PGDATABASE:-nmpa}"
BACKUP_DIR="${BACKUP_DIR:-/backup}"
FULL_BACKUP_RETENTION_WEEKS="${FULL_BACKUP_RETENTION_WEEKS:-4}"
STAMP="$(date +%F_%H%M%S)"
TARGET_FILE="${BACKUP_DIR}/base/base_${PGDATABASE}_${STAMP}.dump"

mkdir -p "${BACKUP_DIR}/base"

echo "[full-backup] start ${TARGET_FILE}"
pg_dump \
  --host="${PGHOST}" \
  --port="${PGPORT}" \
  --username="${PGUSER}" \
  --dbname="${PGDATABASE}" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="${TARGET_FILE}"

retention_days="$(( FULL_BACKUP_RETENTION_WEEKS * 7 ))"
find "${BACKUP_DIR}/base" -mindepth 1 -maxdepth 1 -type f -name "base_*.dump" -mtime +"${retention_days}" -delete
echo "[full-backup] done"
