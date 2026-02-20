#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

POSTGRES_USER="${POSTGRES_USER:-nmpa}"
POSTGRES_DB="${POSTGRES_DB:-nmpa}"
SAFE_UP_SKIP_SNAPSHOT="${SAFE_UP_SKIP_SNAPSHOT:-0}"
SAFE_UP_REQUIRE_SNAPSHOT="${SAFE_UP_REQUIRE_SNAPSHOT:-1}"
SAFE_UP_FORCE="${SAFE_UP_FORCE:-0}"

PRE_SNAPSHOT_DIR="${ROOT_DIR}/backups/postgres/preflight"
mkdir -p "${PRE_SNAPSHOT_DIR}"

echo "[safe-up] running preflight checks"
if ! "${ROOT_DIR}/scripts/db_preflight.sh"; then
  if [[ "${SAFE_UP_FORCE}" != "1" ]]; then
    echo "[safe-up] preflight failed; aborting. Set SAFE_UP_FORCE=1 to continue anyway."
    exit 1
  fi
  echo "[safe-up][WARN] preflight failed, continuing due to SAFE_UP_FORCE=1"
fi

if [[ "${SAFE_UP_SKIP_SNAPSHOT}" != "1" ]]; then
  echo "[safe-up] taking pre-up snapshot"
  docker compose up -d db >/dev/null
  stamp="$(date +%F_%H%M%S)"
  snapshot_file="${PRE_SNAPSHOT_DIR}/${POSTGRES_DB}_pre_up_${stamp}.dump"
  if docker compose exec -T db pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc > "${snapshot_file}"; then
    echo "[safe-up] snapshot saved: ${snapshot_file}"
  else
    echo "[safe-up][ERROR] snapshot failed"
    rm -f "${snapshot_file}" || true
    if [[ "${SAFE_UP_REQUIRE_SNAPSHOT}" == "1" ]]; then
      exit 1
    fi
    echo "[safe-up][WARN] continuing without snapshot due to SAFE_UP_REQUIRE_SNAPSHOT=0"
  fi
else
  echo "[safe-up][WARN] skipping snapshot due to SAFE_UP_SKIP_SNAPSHOT=1"
fi

echo "[safe-up] starting services: docker compose up -d --build $*"
if ! docker compose up -d --build "$@"; then
  echo "[safe-up][ERROR] compose up failed"
  echo "[safe-up] rollback hints:"
  echo "  1) docker compose logs --tail=200"
  echo "  2) docker compose down"
  echo "  3) restore latest preflight dump from ${PRE_SNAPSHOT_DIR}"
  echo "     cat <dump_file> | docker compose exec -T db pg_restore -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
  exit 1
fi

echo "[safe-up] post-check"
if ! "${ROOT_DIR}/scripts/db_preflight.sh"; then
  echo "[safe-up][WARN] post-check failed, inspect immediately."
  exit 1
fi

echo "[safe-up] done"

