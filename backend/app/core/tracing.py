"""
Distributed tracing export. Closes the OTel half of the "metrics/tracing export"
gap that Problem #9 in PHASE_2_REPORT.md left open after wiring Prometheus metrics
-- that round found `opentelemetry-sdk` and `opentelemetry-instrumentation-fastapi`
already in requirements.txt, unwired, from an earlier phase, plus an unused
`OTEL_EXPORTER_OTLP_ENDPOINT` config placeholder. This wires them, and adds the one
package that was still missing entirely: an actual OTLP exporter
(`opentelemetry-exporter-otlp-proto-http`) -- without it, a `TracerProvider` has
spans but nowhere to send them; the prior phase's dependencies could not have
exported anything even if someone had called `.instrument()` on them.

Design goal beyond "spans exist": distributed tracing across the process boundary
this codebase actually has -- API process -> Celery broker -> worker process ->
delivery attempt. A single HTTP-level FastAPI auto-instrumentation would only ever
show one process; the point of tracing here is connecting a `publish_event` request
to the `deliver_webhook` task it eventually causes to run in a *different* process,
which needs explicit W3C trace-context propagation across the queue -- FastAPI/
Celery auto-instrumentation don't do this for each other by default, so it's done
by hand in queue_client.py (inject on enqueue) and tasks.py (extract in the task).

Gating: entirely disabled (no-op, zero overhead, no dependency on a reachable
collector) whenever `OTEL_EXPORTER_OTLP_ENDPOINT` is unset -- the default in every
environment that hasn't explicitly configured one, including the test suite and
local dev. This mirrors the "avoid unnecessary dependencies/infrastructure" pattern
from the rest of this phase: tracing that silently tries to reach a collector at
`localhost:4318` and fails/times out on every request would be worse than no
tracing at all for anyone who hasn't set this up.
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured_provider: Optional[TracerProvider] = None


def setup_tracing(service_name: str) -> TracerProvider | None:
    """
    Idempotent: safe to call more than once (e.g. once per Celery worker process
    via `worker_process_init`, alongside the heartbeat thread) -- only configures
    the global TracerProvider the first time it's actually called with a non-empty
    endpoint in this process; later calls return the already-configured provider
    rather than attaching a second exporter.

    Returns None (tracing fully disabled, no SDK objects created) when
    OTEL_EXPORTER_OTLP_ENDPOINT is unset -- callers must check for None and skip
    instrumentation entirely in that case, not instrument against a no-op provider,
    so that the FastAPI/Celery instrumentation code paths also add zero overhead
    when tracing is off.
    """
    global _configured_provider
    if _configured_provider is not None:
        return _configured_provider

    from app.core.config import settings

    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return None

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _configured_provider = provider
    return provider


def get_tracer(name: str):
    """
    Always returns a usable tracer -- when tracing is disabled (setup_tracing
    returned None, or was never called), `trace.get_tracer` falls back to
    OpenTelemetry's built-in no-op implementation automatically, so call sites
    never need an `if tracing_enabled:` branch around their own span creation.
    """
    return trace.get_tracer(name)
