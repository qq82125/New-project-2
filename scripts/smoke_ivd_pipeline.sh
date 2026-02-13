#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dry-run}" # dry-run | execute
if [[ "$MODE" != "dry-run" && "$MODE" != "execute" ]]; then
  echo "Usage: $0 [dry-run|execute]"
  exit 1
fi

EMAIL="smoke_$(date +%s)@example.com"
PASS="smoke123456"
CLI_SERVICE="${CLI_SERVICE:-api}"  # api | worker

echo "[1/5] register user: ${EMAIL}"
curl -sS -X POST "http://localhost:8000/api/auth/register" \
  -H "content-type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASS}\"}" >/tmp/smoke_register.json || true

echo "[2/5] run one sync"
if ! docker compose exec -T "${CLI_SERVICE}" python -m app.workers.cli sync --once --no-clean-staging; then
  echo "WARN: sync step failed (network/upstream/data issue). continue remaining smoke checks."
fi

echo "[3/5] read status + summary"
curl -sS "http://localhost:8000/api/status" >/tmp/smoke_status.json
curl -sS "http://localhost:8000/api/dashboard/summary?days=30" >/tmp/smoke_summary.json
echo "status saved: /tmp/smoke_status.json"
echo "summary saved: /tmp/smoke_summary.json"

echo "[4/5] reclassify + cleanup (${MODE})"
docker compose exec -T "${CLI_SERVICE}" python -m app.workers.cli reclassify_ivd --dry-run
docker compose exec -T "${CLI_SERVICE}" python -m app.workers.cli cleanup_non_ivd --dry-run --recompute-days 30 --notes "smoke dry-run"
if [[ "$MODE" == "execute" ]]; then
  docker compose exec -T "${CLI_SERVICE}" python -m app.workers.cli reclassify_ivd --execute
  docker compose exec -T "${CLI_SERVICE}" python -m app.workers.cli cleanup_non_ivd --execute --recompute-days 30 --notes "smoke execute"
fi

echo "[5/5] verify"
docker compose exec -T api python - <<'PY'
from sqlalchemy import text
from app.db.session import SessionLocal
s=SessionLocal()
try:
    c_false=s.execute(text("select count(*) from products where is_ivd is false")).scalar_one()
    c_runs=s.execute(text("select count(*) from data_cleanup_runs")).scalar_one()
    print({"products_is_ivd_false": int(c_false), "data_cleanup_runs": int(c_runs)})
finally:
    s.close()
PY

echo "smoke done (${MODE})"
