"""Observability, tracing, and event system for Xeno.

Implements LangSmith-style tracing, structured logging, metrics collection,
and an internal event bus for agent observability.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    AGENT_START = "agent.start"
    AGENT_END = "agent.end"
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    TOOL_ERROR = "tool.error"
    LLM_START = "llm.start"
    LLM_END = "llm.end"
    LLM_TOKEN = "llm.token"
    SUBAGENT_START = "subagent.start"
    SUBAGENT_END = "subagent.end"
    MEMORY_STORE = "memory.store"
    MEMORY_RETRIEVE = "memory.retrieve"
    CHECKPOINT_SAVE = "checkpoint.save"
    CHECKPOINT_RESTORE = "checkpoint.restore"
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_RESPONSE = "approval.response"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class Event:
    id: str
    event_type: EventType
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None


@dataclass
class Span:
    """A trace span representing a unit of work."""
    id: str
    name: str
    event_type: EventType
    start_time: float
    end_time: Optional[float] = None
    parent_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    status: str = "ok"
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def finish(self, status: str = "ok", error: Optional[str] = None) -> None:
        self.end_time = time.time()
        self.status = status
        self.error = error

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.event_type.value,
            "start": self.start_time,
            "end": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
            "events": [
                {"type": e.event_type.value, "data": e.data, "ts": e.timestamp}
                for e in self.events
            ],
        }


class EventBus:
    """Internal event bus for decoupled component communication."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[Event] = []
        self._max_log = 1000

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def publish(self, event_type: str, data: Optional[dict] = None) -> Event:
        """Publish an event."""
        event = Event(
            id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=EventType.CUSTOM if event_type not in [e.value for e in EventType] else EventType(event_type),
            timestamp=time.time(),
            data=data or {},
        )
        self._event_log.append(event)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        return event

    def get_log(self, event_type: Optional[str] = None, limit: int = 50) -> list[Event]:
        """Get recent events."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e.event_type.value == event_type]
        return events[-limit:]


class Tracer:
    """Distributed tracing system for agent operations.

    Tracks spans (units of work) with parent-child relationships,
    capturing timing, metadata, and events.
    """

    def __init__(self, enabled: bool = True, service_name: str = "xeno"):
        self.enabled = enabled
        self.service_name = service_name
        self._spans: dict[str, Span] = {}
        self._active_stack: list[str] = []
        self._completed: list[Span] = []
        self._max_completed = 200

    def start_span(
        self,
        name: str,
        event_type: EventType = EventType.CUSTOM,
        metadata: Optional[dict] = None,
    ) -> str:
        """Start a new trace span."""
        if not self.enabled:
            return ""

        span_id = f"span_{uuid.uuid4().hex[:10]}"
        parent_id = self._active_stack[-1] if self._active_stack else None

        span = Span(
            id=span_id,
            name=name,
            event_type=event_type,
            start_time=time.time(),
            parent_id=parent_id,
            metadata=metadata or {},
        )
        self._spans[span_id] = span
        self._active_stack.append(span_id)
        return span_id

    def end_span(self, span_id: str, status: str = "ok", error: Optional[str] = None) -> Optional[Span]:
        """End a trace span."""
        if not self.enabled or not span_id:
            return None

        span = self._spans.pop(span_id, None)
        if not span:
            return None

        span.finish(status, error)
        self._completed.append(span)

        # Remove from active stack
        if span_id in self._active_stack:
            self._active_stack.remove(span_id)

        # Keep only recent completed spans
        if len(self._completed) > self._max_completed:
            self._completed = self._completed[-self._max_completed:]

        return span

    def add_event(self, span_id: str, event_type: EventType, data: Optional[dict] = None) -> None:
        """Add an event to an active span."""
        if not self.enabled or not span_id:
            return
        span = self._spans.get(span_id)
        if span:
            event = Event(
                id=f"evt_{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=time.time(),
                data=data or {},
            )
            span.events.append(event)

    def trace(
        self,
        name: str,
        event_type: EventType = EventType.CUSTOM,
        metadata: Optional[dict] = None,
    ):
        """Context manager for tracing a block of code."""
        return TraceContext(self, name, event_type, metadata)

    def get_trace_tree(self, root_id: Optional[str] = None) -> list[dict]:
        """Get completed traces as a tree structure."""
        all_spans = list(self._completed)

        # Find root spans (no parent)
        roots = [s for s in all_spans if not s.parent_id]

        def build_tree(span: Span) -> dict:
            children = [s for s in all_spans if s.parent_id == span.id]
            return {
                **span.to_dict(),
                "children": [build_tree(c) for c in children],
            }

        return [build_tree(r) for r in roots]

    def get_stats(self) -> dict[str, Any]:
        """Get tracing statistics."""
        total = len(self._completed)
        if total == 0:
            return {"total_spans": 0}

        durations = [s.duration_ms for s in self._completed]
        errors = sum(1 for s in self._completed if s.status == "error")

        type_counts = defaultdict(int)
        for s in self._completed:
            type_counts[s.event_type.value] += 1

        return {
            "total_spans": total,
            "errors": errors,
            "avg_duration_ms": sum(durations) / total,
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "by_type": dict(type_counts),
        }


class TraceContext:
    """Context manager for automatic span lifecycle."""

    def __init__(self, tracer: Tracer, name: str, event_type: EventType, metadata: Optional[dict]):
        self.tracer = tracer
        self.name = name
        self.span_id: Optional[str] = None

    def __enter__(self) -> str:
        self.span_id = self.tracer.start_span(self.name, metadata=self.metadata if hasattr(self, "metadata") else None)
        return self.span_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.tracer.end_span(self.span_id, status="error", error=str(exc_val))
        else:
            self.tracer.end_span(self.span_id)


class MetricsCollector:
    """Collects and aggregates agent metrics."""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] += value

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def histogram(self, name: str, value: float) -> None:
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> Optional[float]:
        return self._gauges.get(name)

    def get_histogram(self, name: str) -> dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {}
        sorted_vals = sorted(values)
        return {
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[len(sorted_vals) // 2],
            "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
            "p99": sorted_vals[int(len(sorted_vals) * 0.99)],
        }

    def summary(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: self.get_histogram(k) for k in self._histograms},
        }


# Global instances
event_bus = EventBus()
tracer = Tracer()
metrics = MetricsCollector()
