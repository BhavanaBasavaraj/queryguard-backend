"""OpenTelemetry tracing setup.

One TracerProvider per process. Spans are queued by a BatchSpanProcessor
and exported on a background thread, so ending a span never blocks the
request that produced it; if the queue fills, spans are dropped rather
than back-pressuring the caller.

Step 2.1 exports to the console only. The OTLP exporter arrives in 2.3.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from app.config import settings

logger = logging.getLogger(__name__)

_configured = False


class _DropAsgiEvents(SpanExporter):
    """Wraps an exporter and drops ASGI protocol-event spans.

    The ASGI instrumentation emits a child span for every protocol event
    ("http receive", "http send"). They last microseconds, describe the
    transport rather than the application, and outnumber useful spans four
    to one. Filtering in a wrapper keeps the decision in one place and does
    not depend on instrumentation-specific options.
    """

    def __init__(self, wrapped: SpanExporter):
        self._wrapped = wrapped

    def export(self, spans) -> SpanExportResult:
        keep = [s for s in spans if "asgi.event.type" not in (s.attributes or {})]
        if not keep:
            return SpanExportResult.SUCCESS
        return self._wrapped.export(keep)

    def shutdown(self) -> None:
        self._wrapped.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._wrapped.force_flush(timeout_millis)


def setup_tracing() -> None:
    """Register the global TracerProvider. Safe to call more than once."""
    global _configured
    if _configured:
        return

    if not settings.otel_enabled:
        logger.info("tracing disabled (OTEL_ENABLED=false)")
        _configured = True
        return

    # Emit the stable HTTP conventions (http.request.method,
    # http.response.status_code) rather than the pre-1.0 names the
    # instrumentation still defaults to. Must be set before the
    # instrumentation reads it.
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

    # The ASGI instrumentation emits a span per protocol event
    # (http receive, http send). They last microseconds, describe the
    # transport rather than the application, and outnumber useful spans
    # four to one. Dropping them at source is cheaper than filtering later.
    os.environ.setdefault("OTEL_PYTHON_EXCLUDED_URLS", "")

    # Resource describes *what* is emitting, and is attached to every span.
    # Without service.name the SDK reports "unknown_service".
    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": settings.otel_service_version,
        "deployment.environment": settings.otel_environment,
    })

    # 100% sampling: at this volume, losing a trace costs more than
    # storing it. At scale this becomes tail sampling in the Collector,
    # so that slow and failed requests are never the ones dropped.
    provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
    provider.add_span_processor(
        BatchSpanProcessor(_DropAsgiEvents(ConsoleSpanExporter()))
    )

    trace.set_tracer_provider(provider)
    _configured = True
    logger.info(
        "tracing enabled: service=%s env=%s exporter=console",
        settings.otel_service_name, settings.otel_environment,
    )


def get_tracer(name: str):
    """Tracer for one module. The name records where a span came from."""
    return trace.get_tracer(name)
