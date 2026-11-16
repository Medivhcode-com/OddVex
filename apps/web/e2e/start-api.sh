#!/usr/bin/env bash
# Starts the API for end-to-end tests with a throwaway SQLite database and seeded demo data.
set -euo pipefail
PORT="${1:-8210}"
cd "$(dirname "$0")/../../../services/api"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python"
DB="$(mktemp -d)/e2e.db"
export DATABASE_URL="sqlite:///$DB" ODDVEX_ENV="test" ODDVEX_CORS_ORIGINS="http://localhost:3210" ODDVEX_RATE_LIMIT_ENABLED="false" ODDVEX_ADMIN_EMAILS="e2e-admin@oddvex.test" ODDVEX_ALERT_EVAL_MIN_SECONDS="0"
"$PY" -m alembic upgrade head
# Community demo data (fictional profiles with graded picks, and the demo user's profile
# `demo_bettor`) so the community spec has graded records and a rankable leaderboard to render.
# `--with-community` stores both community flags as ON; the two stored overrides are deleted
# again right away, so the API starts with its in-code defaults: both flags OFF. The community
# spec turns them on itself and always turns them off again.
"$PY" scripts/seed_demo.py --with-community
"$PY" - "$DB" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute("DELETE FROM feature_flags WHERE key IN ('community', 'community_leaderboard')")
db.commit()
left = db.execute("SELECT COUNT(*) FROM feature_flags WHERE key LIKE 'community%'").fetchone()[0]
assert left == 0, "community flag overrides were not cleared"
PYEOF
exec "$PY" -m uvicorn oddvex_api.main:app --port "$PORT" --log-level warning
