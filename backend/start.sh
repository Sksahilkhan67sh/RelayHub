#!/bin/sh
# Runs the Celery worker in the background and uvicorn in the foreground,
# inside the SAME Render web service container. This avoids paying for a
# separate Render Background Worker service, at the cost of:
#   - both processes sharing this instance's RAM/CPU (fine for low volume)
#   - if you're on Render's free web tier, the whole container (including
#     the worker) sleeps after 15 min of no HTTP traffic, so queued events
#     won't be delivered until the next request wakes it back up
#   - celery beat (scheduled retries) is NOT included here -- add a third
#     `&` line the same way if you also want automatic retries, or trigger
#     retries manually for now

set -e

alembic upgrade head

celery -A app.workers.celery_app worker --loglevel=info &
WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} &
API_PID=$!

# If either process dies, kill the other and exit so Render restarts the container
wait -n "$WORKER_PID" "$API_PID"
exit $?