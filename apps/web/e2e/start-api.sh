#!/usr/bin/env bash
# Starts the API for end-to-end tests with a throwaway SQLite database and seeded demo data.
set -euo pipefail
PORT="${1:-8210}"
cd "$(dirname "$0")/../../../services/api"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python"
DB="$(mktemp -d)/e2e.db"
export DATABASE_URL="sqlite:///$DB" ODDVEX_ENV="test" ODDVEX_CORS_ORIGINS="http://localhost:3210" ODDVEX_RATE_LIMIT_ENABLED="false"
"$PY" -m alembic upgrade head
"$PY" scripts/seed_demo.py
exec "$PY" -m uvicorn oddvex_api.main:app --port "$PORT" --log-level warning
