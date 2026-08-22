"""
Tests for app/core/tracing.py. Two things matter here:

1. Tracing is a true no-op (no exception, no attempted network call) whenever
   OTEL_EXPORTER_OTLP_ENDPOINT is unset -- the default in every environment that
   hasn't explicitly configured a collector, including this test suite itself.
2. When tracing IS configured, the context-propagation roundtrip actually works:
   injecting a span's context into a carrier (as queue_client.py does before
   dispatching to Celery) and extracting it back out (as tasks.py does inside the
   worker) must reconstruct the same trace, or distributed tracing across the
   queue boundary is broken even though spans exist.

Neither test makes a real network call to a collector -- test 2 substitutes an
InMemorySpanExporter for the real OTLP exporter, which is the standard OTel testing
pattern for verifying export/propagation logic without a live collector.
"""

from __future__ import annotations

import importlib

import pytest
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def _reset_tracing_module():
    """
    app/core/tracing.py caches the configured provider at module level
    (`_configured_provider`) so `setup_tracing` is idempotent within one process.
    Tests need a clean slate each time to actually exercise both the
    "unconfigured" and "configured" branches, so reload the module and reset
    OTel's own global tracer-provider state around every test in this file.

    OTel deliberately only allows `set_tracer_provider` to succeed once per
    process (an `Once` guard, not just the `_TRACER_PROVIDER` reference itself) --
    resetting only the reference and not the guard would make every test after the
    first `set_tracer_provider` call silently no-op instead of actually installing
    the new provider, which would make these tests pass for the wrong reason.
    """
    import app.core.tracing as tracing_module

    yield
    importlib.reload(tracing_module)
    trace._TRACER_PROVIDER = None  # noqa: SLF001 -- test isolation only
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001 -- test isolation only


def test_setup_tracing_is_a_noop_when_endpoint_unset(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "")

    import app.core.tracing as tracing_module

    result = tracing_module.setup_tracing("relayhub-test")
    assert result is None

    # get_tracer must still work and produce a usable (no-op) span -- callers in
    # tasks.py/celery_app.py never branch on whether tracing is enabled.
    tracer = tracing_module.get_tracer(__name__)
    with tracer.start_as_current_span("does-nothing") as span:
        assert span is not None


def test_setup_tracing_is_idempotent(monkeypatch):
    """A second call in the same process must not attach a second exporter/provider."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    import app.core.tracing as tracing_module

    first = tracing_module.setup_tracing("relayhub-test")
    second = tracing_module.setup_tracing("relayhub-test")
    assert first is not None
    assert first is second


def test_trace_context_roundtrips_across_inject_extract():
    """
    Simulates the exact propagation queue_client.py (inject) and tasks.py (extract)
    do across the API-process -> Celery-broker -> worker-process boundary, using an
    in-memory exporter instead of a real OTLP collector.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "test-api"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer(__name__)

    # --- API-process side: publish_event's request span, then inject before enqueue ---
    carrier: dict[str, str] = {}
    with tracer.start_as_current_span("publish_event") as api_span:
        api_trace_id = api_span.get_span_context().trace_id
        inject(carrier)  # what queue_client.py's enqueue() does

    assert "traceparent" in carrier, "inject() must populate the carrier with a real span active"

    # --- worker-process side: extract, then continue the trace ---
    parent_ctx = extract(carrier)  # what tasks.py's deliver_webhook does
    with tracer.start_as_current_span("deliver_webhook", context=parent_ctx) as worker_span:
        worker_trace_id = worker_span.get_span_context().trace_id

    # The whole point: the worker's span is part of the SAME trace as the API
    # request that caused it, not a disconnected new one.
    assert worker_trace_id == api_trace_id


def test_extract_with_missing_headers_is_safe():
    """
    tasks.py calls `extract(self.request.headers or {})` -- Celery's
    `self.request.headers` is None when a task was dispatched without custom
    headers (e.g. tracing disabled, so queue_client.py passed headers=None).
    Must not raise.
    """
    parent_ctx = extract({})
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("deliver_webhook", context=parent_ctx) as span:
        assert span is not None
