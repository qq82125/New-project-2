#!/usr/bin/env bash
set -euo pipefail

proj="${IT_COMPOSE_PROJECT:-ivd_it_pg}"
compose_file="docker-compose.it.yml"

export IT_DATABASE_URL="${IT_DATABASE_URL:-postgresql+psycopg://it_nmpa:it_nmpa@127.0.0.1:55432/it_nmpa}"

docker compose -p "$proj" -f "$compose_file" up -d --wait

cleanup() {
  docker compose -p "$proj" -f "$compose_file" down -v
}
trap cleanup EXIT

(
  cd api
  export PYTHONPATH=.
  python3 -m pytest -q tests/test_cleanup_rollback_integration_pg.py
  python3 -m pytest -q tests/test_pr5_classify_cleanup_rollback_integration_pg.py
  python3 -m pytest -q tests/test_pr1_tables_integration_pg.py
  python3 -m pytest -q tests/test_nhsa_ingest_integration_pg.py
)
