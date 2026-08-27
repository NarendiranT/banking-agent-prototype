"""OpenTelemetry tracing and metrics for the banking agent."""

from __future__ import annotations

import atexit
import os
from functools import wraps
from typing import Any, Callable

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode

INSTRUMENTATION_NAME = "banking-agent"
SERVICE_VERSION = "1.0.0"

_initialized = False


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def telemetry_enabled() -> bool:
    if os.getenv("OTEL_ENABLED") is not None:
        return _env_flag("OTEL_ENABLED")
    return bool(
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or _env_flag("OTEL_CONSOLE_EXPORTER")
    )


def setup_telemetry(service_name: str) -> None:
    """Initialize tracing and metrics once per process."""
    global _initialized
    if _initialized or not telemetry_enabled():
        return

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
            "service.version": SERVICE_VERSION,
            "deployment.environment": os.getenv(
                "OTEL_ENVIRONMENT",
                "local",
            ),
        }
    )

    provider = TracerProvider(resource=resource)
    console_only = _env_flag("OTEL_CONSOLE_EXPORTER") and not (
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )
    if not console_only:
        # Uses OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4318).
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        metrics.set_meter_provider(
            MeterProvider(
                resource=resource,
                metric_readers=[
                    PeriodicExportingMetricReader(OTLPMetricExporter())
                ],
            )
        )

    if _env_flag("OTEL_CONSOLE_EXPORTER"):
        provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )

    trace.set_tracer_provider(provider)
    _instrument_libraries()
    atexit.register(shutdown_telemetry)
    _initialized = True


def _instrument_libraries() -> None:
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    RequestsInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)


def instrument_fastapi(app) -> None:
    if not telemetry_enabled():
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,/health",
        exclude_spans=["receive", "send"],
    )


def instrument_starlette() -> None:
    if not telemetry_enabled():
        return
    from opentelemetry.instrumentation.starlette import StarletteInstrumentor

    StarletteInstrumentor().instrument()


def get_tracer():
    return trace.get_tracer(INSTRUMENTATION_NAME, SERVICE_VERSION)


def get_meter():
    return metrics.get_meter(INSTRUMENTATION_NAME, SERVICE_VERSION)


def set_span_attributes(**attrs: Any) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    for key, value in attrs.items():
        if value is None or value == "":
            continue
        if isinstance(value, (bool, int, float, str)):
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, str(value))


def _is_graph_interrupt(exc: BaseException) -> bool:
    name = type(exc).__name__
    return "Interrupt" in name or "BubbleUp" in name


def traced(span_name: str, **static_attrs: Any) -> Callable:
    """Create an async span around a function. Graph interrupts are not errors."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any):
            with get_tracer().start_as_current_span(
                span_name,
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                for key, value in static_attrs.items():
                    span.set_attribute(key, value)
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    if _is_graph_interrupt(exc):
                        span.set_attribute("langgraph.interrupted", True)
                        raise
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

        return wrapper

    return decorator


def traced_graph_node(name: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(state: Any, *args: Any, **kwargs: Any):
            with get_tracer().start_as_current_span(
                f"graph.node.{name}",
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                span.set_attribute("langgraph.node.name", name)
                if isinstance(state, dict):
                    set_span_attributes(
                        **{
                            "banking.intent": state.get("intent"),
                            "banking.source_account": state.get(
                                "source_account"
                            ),
                            "banking.user_id": state.get("user_id"),
                        }
                    )
                try:
                    result = await fn(state, *args, **kwargs)
                    if isinstance(result, dict):
                        set_span_attributes(
                            **{
                                "banking.intent": result.get("intent"),
                                "banking.has_answer": bool(
                                    result.get("answer")
                                ),
                            }
                        )
                    return result
                except Exception as exc:
                    if _is_graph_interrupt(exc):
                        span.set_attribute("langgraph.interrupted", True)
                        raise
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

        return wrapper

    return decorator


def shutdown_telemetry() -> None:
    global _initialized
    if not _initialized:
        return
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
    meter_provider = metrics.get_meter_provider()
    if hasattr(meter_provider, "shutdown"):
        meter_provider.shutdown()
    _initialized = False
