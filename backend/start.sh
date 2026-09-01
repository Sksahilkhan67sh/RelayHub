#!/bin/sh
# Runs the Celery worker, Celery beat, and uvicorn in the background/foreground,
# all inside the SAME Render web service container. This avoids paying for
# separate Render Background Worker services, at the cost of:
#   - all three processes sharing this instance's RAM/CPU (fine for low volume)
#   - if you're on Render's free web tier, the whole container (including the
#     worker and beat) sleeps after 15 min of no HTTP traffic, so queued events
#     and scheduled retries won't be delivered until the next request wakes it
#     back up
#
# G-RETRY-1 fix: this used to run only the worker + uvicorn, with a comment
# saying beat (scheduled retries) was deliberately left out. That meant a
# job's *first* attempt always ran fine (dispatched straight to the worker at
# publish time, in app/modules/events/service.py), but nothing ever re-enqueued
# it for a 2nd/3rd/... attempt: check_due_retries (app/modules/retry/scheduler.py)
# only runs because Celery Beat's beat_schedule (app/workers/celery_app.py)
# fires it every 10s -- with no beat process anywhere in this deployment, that
# task never ran, so every job that failed its first attempt sat in
# status=retrying forever with a next_attempt_at in the past that nothing ever
# noticed. Confirmed: relayhub-backend on Render ran only this script with no
# separate beat service alongside it.
#
# NOTE: uses plain POSIX `sh` syntax throughout (no `wait -n`, which is a
# bash-only feature and is NOT available in the dash/sh Render actually runs).

set -e

echo "===DEBUG HOST: $(python3 -c "import re,os; print(re.search(r'@([^:/]+)', os.environ.get('DATABASE_URL','MISSING')).group(1) if os.environ.get('DATABASE_URL') else 'MISSING')")==="

alembic upgrade head

celery -A app.workers.celery_app worker --loglevel=info --pool=solo --concurrency=1 &
WORKER_PID=$!

celery -A app.workers.celery_app beat --loglevel=info &
BEAT_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} &
API_PID=$!

# Poll every 2s; if any of the three has died, kill the rest and exit non-zero
# so Render notices the container exited and restarts it.
while kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$BEAT_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 2
done

kill "$WORKER_PID" "$BEAT_PID" "$API_PID" 2>/dev/null || true
exit 1
