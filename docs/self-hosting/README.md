# Self-Hosting RelayHub

This guide covers the **only deployment path that actually exists in this
repository today**: local Docker Compose, defined in
`infra/docker/docker-compose.yml`. It runs Postgres, Redis, the FastAPI API, and
two Celery containers (worker + beat).

**What this guide does not cover, because it isn't implemented yet:**
Kubernetes (`infra/k8s` is an empty directory), an Nginx reverse-proxy config
(`infra/nginx` is empty), Grafana dashboards (`infra/grafana` is empty), and TLS
termination -- none of these exist in the repository. Each is called out below
as **Planned / Not currently implemented** where relevant, with what it would
take to add.

Also note: **the frontend (`apps/web`) has no service in `docker-compose.yml`**.
Only the backend, its two Celery processes, and its two datastores are covered
by Compose. Run the frontend separately (see "Frontend" below).

## Prerequisites

- Docker and Docker Compose (v2 syntax, `docker compose ...`)
- Node.js 18+ and npm, if you also want to run the frontend
- Python 3.12+, only if you want to run the backend outside Docker (Compose
  handles this for you otherwise)

## Repository setup

```bash
git clone <this repository>
cd relayhub
cp backend/.env.example backend/.env
```

## Environment variables

Edit `backend/.env`. Every variable below is read by
`backend/app/core/config.py` -- nothing here is invented. Two have no default
and **must** be set or the API fails to start (`SECRET_KEY`,
`ENCRYPTION_MASTER_KEY`, `DATABASE_URL`):

| Variable | Default | Notes |
|---|---|---|
| `ENV` | `development` | `development` \| `staging` \| `production` |
| `DEBUG` | `false` | |
| `SECRET_KEY` | *(required)* | JWT signing key. Generate: `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | |
| `DATABASE_URL` | *(required)* | `postgresql+asyncpg://relayhub:relayhub@postgres:5432/relayhub` for Compose |
| `REDIS_URL` | `redis://localhost:6379/0` | general cache/queue |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | separate Redis DB index |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | separate Redis DB index |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array |
| `ENCRYPTION_MASTER_KEY` | *(required)* | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BLOCK_PRIVATE_IP_TARGETS` | `true` | SSRF protection for endpoint URLs -- leave `true` unless you have a specific reason not to |
| `ALLOW_HTTP_ENDPOINTS_IN_DEV` | `true` | allows non-HTTPS endpoint URLs; set `false` in production |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | empty | leave empty to run without billing enforcement in dev |
| `RESEND_API_KEY` / `EMAIL_FROM_ADDRESS` | empty / `RelayHub <alerts@relayhub.dev>` | leave `RESEND_API_KEY` empty and password-reset/invite emails will fail to send but the API will still start. Uses Resend's HTTP API (not SMTP) -- SMTP is blocked outbound by many PaaS free tiers |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty | see Observability note below -- setting this alone does not enable tracing, no exporter code is wired up yet |
| `LOG_LEVEL` | `INFO` | |

## Starting everything

```bash
cd infra/docker
docker compose up --build
```

This builds the backend image, starts Postgres and Redis (waiting for their
healthchecks), then starts the API, the Celery worker, and Celery beat. The API
container's start command runs migrations automatically before starting
uvicorn:

```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

So there is no separate "run migrations" step for Compose users -- it's part of
the `api` service's command. (If you run the backend outside Compose, run
`alembic upgrade head` yourself first.)

## Frontend

Not part of `docker-compose.yml`. Run it separately, pointed at the API
container's exposed port:

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Health checks

- **Postgres:** `pg_isready -U relayhub` (Compose healthcheck, every 5s)
- **Redis:** `redis-cli ping` (Compose healthcheck, every 5s)
- **API:** `GET http://localhost:8000/health/live` -- also the image's `HEALTHCHECK` directive in `backend/Dockerfile`

```bash
curl http://localhost:8000/health/live
```

## Logs

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f beat
```

`LOG_LEVEL` in `.env` controls verbosity (`INFO` by default).

## Data persistence

Postgres data is persisted in the named Docker volume `pgdata` (declared at the
bottom of `docker-compose.yml`). Redis has no volume configured, so its data
(queue state, cache, Celery broker/results) does **not** survive a
`docker compose down -v` or a container recreation without the volume flag --
this is acceptable for queue/cache data by nature, but be aware nothing in
Redis is durable across a full teardown.

## Backup considerations

There is no built-in backup tooling in this repository. For Postgres, use
standard `pg_dump`/`pg_restore` against the `postgres` container:

```bash
docker compose exec postgres pg_dump -U relayhub relayhub > backup.sql
docker compose exec -T postgres psql -U relayhub relayhub < backup.sql
```

Back up before any `alembic upgrade` in production, same as any schema-migrating system.

## Shutdown

```bash
docker compose down          # stop containers, keep the pgdata volume
docker compose down -v       # stop containers AND delete the pgdata volume (destroys your database)
```

## Troubleshooting

- **API container exits immediately on startup:** almost always a missing
  required env var (`SECRET_KEY`, `ENCRYPTION_MASTER_KEY`, or `DATABASE_URL`)
  or a malformed `ENCRYPTION_MASTER_KEY` (must be a valid Fernet key, not an
  arbitrary string). Check `docker compose logs api`.
- **`alembic upgrade head` fails on first boot:** confirm the `postgres`
  service is actually healthy first (`docker compose ps`) -- the `api` service
  depends on `postgres`'s healthcheck, but if Postgres is slow to initialize on
  first volume creation this can still race.
- **Password reset / invitation emails never arrive:** `RESEND_API_KEY` is empty by
  default. Set it to a real Resend API key to receive them; without
  it, the API still returns success responses (the generic "if this email
  exists" message on `/auth/forgot-password`) but nothing is actually sent.
- **Deliveries never leave `queued`:** confirm the `worker` container is
  running and healthy (`docker compose ps`) -- delivery execution is entirely
  the Celery worker's job, not the API process.
- **Retries never fire:** confirm the `beat` container is running -- retry
  scheduling depends on `check_due_retries`, which only runs if Celery beat is up.

## Scaling

The `worker` service can be scaled horizontally with Compose's `--scale` flag
(`docker compose up --scale worker=3`) since delivery execution is
stateless and coordinated entirely through the Redis queue. `beat` must run as
exactly one instance (running multiple beat schedulers would double-schedule
tasks) -- this is a Celery constraint, not something this repository works
around.

## Kubernetes, Nginx, Grafana

**Planned / Not currently implemented.** `infra/k8s`, `infra/nginx`, and
`infra/grafana` exist as empty directories in this repository -- there are no
manifests, no reverse-proxy config, and no dashboards to document. Adding any of
these is future infrastructure work, not a gap in this guide.
