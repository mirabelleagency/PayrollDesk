#!/bin/sh
set -e
# Print useful debug info for startup logs
echo "[entrypoint] starting at $(date -u)"
echo "[entrypoint] working dir: $(pwd)"
echo "[entrypoint] python: $(python -V 2>&1)"
# Only known-safe variables. The old deny-list printed every variable whose
# name didn't match a fixed pattern, so a newly added secret ended up in logs.
echo "[entrypoint] environment (allow-listed):"
env | sort | grep -E '^(ENVIRONMENT|PORT|PYTHON_VERSION|LANG|HOME|PWD|RENDER_(GIT_BRANCH|GIT_COMMIT|SERVICE_NAME|SERVICE_TYPE|INSTANCE_ID|EXTERNAL_URL|CPU_COUNT|WEB_CONCURRENCY))=' || true

# Bring the schema up to date. A fresh database gets the full schema and is
# stamped at head; otherwise `alembic upgrade head`. A failed migration stops the
# deploy here: carrying on ran the app against a half-migrated schema and hid
# the failure in the logs.
echo "[entrypoint] migrating database..."
python -m app.db_bootstrap || {
    echo "[entrypoint] FATAL: database migration failed, not starting"
    exit 1
}

# Load the app once before gunicorn binds the port. If it cannot import (a
# missing driver, a bad config), the deploy fails here and the port never opens,
# rather than gunicorn listening while every worker crashes on boot.
echo "[entrypoint] checking the app loads..."
python -c "import app.main" || {
    echo "[entrypoint] FATAL: app failed to load, not starting"
    exit 1
}

# Default port if not set
if [ -z "$PORT" ]; then
  PORT=8000
fi

# Worker count: Render sizes it to the instance (1 on the free plan's 0.15 CPU,
# where a second worker only doubled the boot time). Default 2 elsewhere.
WORKERS="${WEB_CONCURRENCY:-${RENDER_WEB_CONCURRENCY:-2}}"

echo "[entrypoint] launching gunicorn on 0.0.0.0:$PORT with $WORKERS worker(s)"

exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers "$WORKERS" --log-level info
