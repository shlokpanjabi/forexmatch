#!/usr/bin/env bash
# Start ForexMatch locally: checks the database, applies migrations, seeds the
# catalogue if empty, then runs the API and the frontend together.
#
#   ./scripts/dev.sh              # API on :8000, frontend on :3000
#   ./scripts/dev.sh --api-only   # just the API
#
# Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
API_ONLY=false
[[ "${1:-}" == "--api-only" ]] && API_ONLY=true

PG_BIN="${PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
[[ -d "$PG_BIN" ]] && export PATH="$PG_BIN:$PATH"

VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "No virtualenv at $VENV. Create one:" >&2
  echo "  python3.13 -m venv .venv && .venv/bin/pip install -e 'backend[dev]'" >&2
  exit 1
fi

# --- Database ---------------------------------------------------------------
echo "==> Checking PostgreSQL"
if ! pg_isready -q 2>/dev/null; then
  echo "PostgreSQL is not running. Start it with:" >&2
  echo "  brew services start postgresql@17" >&2
  echo "  (or: docker compose up -d postgres)" >&2
  exit 1
fi
createdb forexmatch 2>/dev/null || true

echo "==> Applying migrations"
(cd "$ROOT/backend" && "$VENV/bin/alembic" upgrade head >/dev/null)

CARDS=$(psql -d forexmatch -Atc "select count(*) from cards;" 2>/dev/null || echo 0)
if [[ "$CARDS" -eq 0 ]]; then
  echo "==> Seeding the card catalogue"
  (cd "$ROOT/backend" && "$VENV/bin/python" scripts/seed_cards.py)
else
  echo "==> Catalogue already loaded ($CARDS cards)"
fi

# --- Processes --------------------------------------------------------------
PIDS=()
cleanup() {
  echo
  echo "==> Stopping"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> API on http://localhost:$API_PORT"
(cd "$ROOT/backend" && "$VENV/bin/uvicorn" app.main:app --port "$API_PORT" --reload) &
PIDS+=($!)

if [[ "$API_ONLY" == false ]]; then
  echo "==> Frontend on http://localhost:$WEB_PORT"
  (cd "$ROOT/frontend" && npm run dev -- --port "$WEB_PORT") &
  PIDS+=($!)
fi

echo
echo "Ready. Ctrl-C to stop."
wait
