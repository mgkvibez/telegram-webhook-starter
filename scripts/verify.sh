#!/usr/bin/env bash
# Local gate. Run this before you push: ./scripts/verify.sh
# It is the same four things CI does, plus a real server smoke test.
set -uo pipefail
cd "$(dirname "$0")/.."

fail() { echo; echo "GATE FAILED: $*" >&2; exit 1; }
step() { echo; echo "== $*"; }

step "1/6 python version (>= 3.10, PEP 604 annotations)"
python3 - <<'PY' || fail "python too old"
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
python3 --version

step "2/6 dependencies"
python3 -c "import fastapi, httpx, uvicorn" 2>/dev/null || fail "run: pip install -r requirements-dev.txt"

step "3/6 ruff"
python3 -m ruff check . || fail "ruff"

step "4/6 tests (offline, no network, no token)"
python3 -m pytest -q || fail "tests"

step "5/6 the app imports with an empty environment"
env -i PATH="$PATH" python3 -c "import app; app.app; print('import ok, no env needed')" || fail "import smoke"

step "6/6 live server smoke (uvicorn, real HTTP, then shut down)"
PORT=8137
BOT_TOKEN="123:TEST" WEBHOOK_SECRET="gate-secret" ADMIN_TOKEN="gate-admin" \
  python3 -m uvicorn app:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
for _ in $(seq 1 40); do
  sleep 0.25
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then break; fi
done
grep -q '"configured":true' <(curl -fsS "http://127.0.0.1:$PORT/health") || fail "health did not report configured"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/webhook" -d '{}' \
  -H 'Content-Type: application/json')
[ "$CODE" = "401" ] || fail "webhook without a secret header should be 401, got $CODE"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/webhook" -d '{}' \
  -H 'Content-Type: application/json' -H 'X-Telegram-Bot-Api-Secret-Token: gate-secret')
[ "$CODE" = "400" ] || fail "webhook with a valid secret and junk body should be 400, got $CODE"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/admin/webhook-info")
[ "$CODE" = "401" ] || fail "admin route without a bearer should be 401, got $CODE"
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
echo "server responded correctly and was shut down"

step "gardening: no polling loop anywhere (this project is webhooks only)"
grep -rn "getUpdates" --include=*.py . && fail "getUpdates found: this bot must not poll"

echo
echo "GATE PASSED: $(python3 -m pytest -q 2>/dev/null | grep -E '[0-9]+ (passed|failed)' | tail -1)"
