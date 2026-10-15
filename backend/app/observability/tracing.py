from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from app.core import config

SERVICE_NAME = "campus-copilot-backend"


def setup_tracing(app, engine, exporter: SpanExporter | None = None) -> TracerProvider | None:
    """Trace every request and every database query, if a collector is configured.

    exporter lets a test capture spans in memory instead of sending them anywhere."""
    if exporter is None:
        if not config.OTEL_EXPORTER_OTLP_ENDPOINT:
            return None
        exporter = OTLPSpanExporter()  # reads OTEL_EXPORTER_OTLP_ENDPOINT itself
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME, "deployment.environment": config.ENVIRONMENT}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="health,metrics")
    # The instrumentation package declares support up to SQLAlchemy 2.0, and refuses to start on the 2.1 this
    # project uses unless told not to check. It works through SQLAlchemy's event hooks, which 2.1 still has;
    # a test checks that a query really produces a span, so a future break shows up.
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider, skip_dep_check=True)
    return provider
