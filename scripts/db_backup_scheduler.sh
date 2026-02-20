#!/usr/bin/env bash
set -euo pipefail

BACKUP_RUN_AT="${BACKUP_RUN_AT:-03:30}"           # HH:MM
FULL_BACKUP_WEEKDAY="${FULL_BACKUP_WEEKDAY:-1}"   # 1=Mon ... 7=Sun
STATE_FILE="${BACKUP_DIR:-/backup}/.last_backup_run_date"

mkdir -p "${BACKUP_DIR:-/backup}"

echo "[backup-scheduler] run_at=${BACKUP_RUN_AT} full_backup_weekday=${FULL_BACKUP_WEEKDAY}"

while true; do
  now_date="$(date +%F)"
  now_time="$(date +%H:%M)"
  last_date=""
  if [[ -f "${STATE_FILE}" ]]; then
    last_date="$(cat "${STATE_FILE}" || true)"
  fi

  if [[ "${now_time}" == "${BACKUP_RUN_AT}" && "${last_date}" != "${now_date}" ]]; then
    echo "[backup-scheduler] daily cycle start date=${now_date} time=${now_time}"
    sh /scripts/backup_pg_wal_daily.sh

    weekday="$(date +%u)"
    if [[ "${weekday}" == "${FULL_BACKUP_WEEKDAY}" ]]; then
      sh /scripts/backup_pg_weekly_full.sh
    fi

    echo "${now_date}" > "${STATE_FILE}"
    echo "[backup-scheduler] daily cycle done date=${now_date}"
    sleep 65
    continue
  fi

  sleep 20
done
