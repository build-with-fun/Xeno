"""Observability and monitoring for Xeno agents.

Provides:
- Distributed tracing via OpenTelemetry-compatible spans
- Metrics collection (token usage, latency, error rates)
- Event exporters (console, file, HTTP)
"""

from xeno.observability.tracer import Tracer, get_tracer, TraceSpan
from xeno.observability.metrics import MetricsCollector, get_metrics
from xeno.observability.exporter import ConsoleExporter, FileExporter, CompositeExporter
