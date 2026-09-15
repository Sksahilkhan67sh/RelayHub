"""
Structured (JSON) logging, with request/correlation context automatically
attached to every log record.

Phase 3 observability gap: every module already does `logger =
logging.getLogger(__name__)` and logs operationally useful lines (delivery
job IDs, status, worker IDs -- see e.g. app/workers/tasks.py), but nothing in
the codebase ever configured Python's logging module itself. Unconfigured,
these fall through to the interpreter's "handler of last resort" -- plain
text, not machine-parseable, and with no request_id/correlation context
attached unless each call site manually interpolates it (most don't).

Design: a `logging.Filter` reads from a contextvar (`request_id_var`) and
stamps it onto every `LogRecord` that passes through, whether or not the
logging call site itself knows anything about requests. A contextvar
(not a plain module-level global) is what makes this safe under FastAPI's
concurrent request handling: each `asyncio` task gets its own copy,
automatically isolated from every other in-flight request -- see
`RequestIDMiddleware` (app/middleware/request_id.py), which sets it once per
request, and this module's own regression tests, which prove two concurrent
requests never see each other's context.

Deliberately minimal: this does not rewrite every existing log call in the
codebase (the brief explicitly says not to). It configures the formatter and
the automatic request_id attachment; call sites that want additional
structured fields (job_id, organization_id, etc.) already pass them via %s
interpolation into the message, which remains fully readable in the `message`
field of the resulting JSON -- upgrading specific hot-path/operationally-
important call sites to pass fields as `extra={...}` instead is left for
follow-up work where it's actually needed, not applied uniformly here.
"""
from __future__ import annotations

import contextvars
import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

# Extra, optional correlation fields a call site (or a background task) can set
# for the duration of its own work -- same contextvar mechanism as request_id,
# same per-async-task isolation guarantee. Not required; None is omitted from
# the rendered JSON rather than emitted as a literal "null".
job_context_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("job_context", default=None)

_STANDARD_LOGRECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {"message"}


class RequestContextFilter(logging.Filter):
    """Attaches request_id (and any active job_context fields) to every record
    that passes through a handler with this filter installed."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id is not None:
            record.request_id = request_id
        job_context = job_context_var.get()
        if job_context:
            for key, value in job_context.items():
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Includes any extra fields a call site passed
    via `logger.info(..., extra={...})` or that RequestContextFilter attached,
    alongside the standard timestamp/level/logger/message fields.

    Never includes exc_info's raw traceback text unless the call site used
    logger.exception()/logger.error(exc_info=True) -- same as normal logging
    behavior, just rendered as a "traceback" field instead of appended text,
    so it stays queryable rather than swallowing the rest of the line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOGRECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(*, json_format: bool | None = None) -> None:
    """Idempotent (safe to call once per FastAPI process and once per Celery
    worker child process, same pattern as app/core/tracing.py's setup_tracing
    and celery_app.py's heartbeat thread) -- only configures the root logger
    the first time it's actually called in a given process.

    `json_format` defaults to True everywhere except local interactive/test
    runs (ENV == "test" or "development"), where plain text is easier to read
    at a terminal; explicit True/False always wins over that default, e.g. for
    an operator who wants to eyeball JSON locally too.
    """
    global _configured
    if _configured:
        return
    _configured = True

    from app.core.config import settings

    if json_format is None:
        json_format = settings.ENV not in ("test", "development")

    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        JsonFormatter() if json_format else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    # Quiet down noisy third-party loggers that would otherwise dominate
    # output at INFO -- operational signal, not a behavior change.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def set_job_context(**fields: Any) -> contextvars.Token:
    """For background/worker code that wants log lines tagged with e.g.
    job_id=..., worker_id=... without threading those through every logger
    call manually. Returns a token; pass it to `reset_job_context` when the
    unit of work is done (mirrors contextvars' own reset API) so the context
    doesn't leak into whatever this async task (or thread) does next."""
    return job_context_var.set({k: v for k, v in fields.items() if v is not None})


def reset_job_context(token: contextvars.Token) -> None:
    job_context_var.reset(token)
