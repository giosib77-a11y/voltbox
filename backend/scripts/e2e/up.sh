#!/usr/bin/env bash
# Put the e2e system back to "the day the shop opened" and start it.
#
# The run has to begin from an empty database every time: the story it walks
# starts with a shop that has nothing in it, and a leftover product from a
# previous attempt turns the first assertion into a lie.
set -u

# The backend directory, wherever this checkout lives.
BACKEND=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PY="$BACKEND/.venv/Scripts/python.exe"
DB="postgresql://voltbox:voltbox@localhost:55432/voltbox_e2e"

cd "$BACKEND" || exit 1

# The server holds connections open, and DROP DATABASE fails while it does.
PID=$(netstat -ano 2>/dev/null | grep ":8100" | grep LISTENING | awk '{print $5}' | head -1)
if [ -n "${PID:-}" ]; then
  powershell -Command "Stop-Process -Id $PID -Force" 2>/dev/null
  sleep 2
fi

docker exec voltbox-pg psql -U voltbox -d postgres \
  -c "drop database if exists voltbox_e2e;" -c "create database voltbox_e2e;" >/dev/null || exit 1

DATABASE_URL="$DB" APP_ENV=test "$PY" -m alembic upgrade head >/dev/null 2>&1 || exit 1

PYTHONIOENCODING=utf-8 DATABASE_URL="$DB" APP_ENV=development \
  VOLTBOX_ADMIN_PASSWORD='Thunder-Vault-91' \
  "$PY" scripts/manage_admin.py create-admin \
  --email owner@voltbox.ge --first-name ნინო --last-name ლომიძე >/dev/null 2>&1 || exit 1

# SUPABASE_* blanked: backend/.env carries real credentials, and without this
# the run uploads product photos into the live bucket. Learned the hard way.
DATABASE_URL="$DB" APP_ENV=development SITE_URL=http://localhost:4173 \
  CORS_ORIGINS=http://localhost:4173 SUPABASE_PROJECT_REF= SUPABASE_SERVICE_ROLE_KEY= \
  "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --log-level warning \
  >/tmp/voltbox-e2e-api.log 2>&1 &

for _ in $(seq 1 30); do
  if curl -sf -o /dev/null http://127.0.0.1:8100/api/v1/health; then
    echo "ready"
    exit 0
  fi
  sleep 0.5
done

echo "the API never came up"
tail -5 /tmp/voltbox-e2e-api.log
exit 1
