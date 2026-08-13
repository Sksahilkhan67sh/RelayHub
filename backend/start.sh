#!/bin/sh
# Runs the Celery worker in the background and uvicorn in the foreground,
# inside the SAME Render web service container. This avoids paying for a
# separate Render Background Worker service, at the cost of:
#   - both processes sharing this instance's RAM/CPU (fine for low volume)
#   - if you're on Render's free web tier, the whole container (including
#     the worker) sleeps after 15 min of no HTTP traffic, so queued events
#     won't be delivered until the next request wakes it back up
#   - celery beat (scheduled retries) is NOT included here -- add a third
#     background process the same way if you also want automatic retries
#
# NOTE: uses plain POSIX `sh` syntax throughout (no `wait -n`, which is a
# bash-only feature and is NOT available in the dash/sh Render actually runs).

set -e

alembic upgrade head

celery -A app.workers.celery_app worker --loglevel=info --pool=solo --concurrency=1 &
WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} &
API_PID=$!

# Poll every 2s; if either process has died, kill the other and exit non-zero
# so Render notices the container exited and restarts it.
while kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 2
done

kill "$WORKER_PID" "$API_PID" 2>/dev/null || true
exit 1
