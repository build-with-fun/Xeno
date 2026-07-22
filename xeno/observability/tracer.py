from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TRACER: Optional["Tracer"] = None


def get_tracer() -> "Tracer":
    global _TRACER
    if _TRACER is None:
        _TRACER = Tracer()
    return _TRACER


@dataclass
class TraceSpan:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str = ""

    @property
    def duration_ms(self) -> float:
        if self.end_time == 0:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


class Tracer:
    """Simple distributed tracer for agent operations.

    Creates spans for agent runs, tool calls, sub-agent tasks, etc.
    Supports parent-child span relationships for full trace trees.
    """

    def __init__(self):
        self._spans: dict[str, TraceSpan] = {}
        self._active_spans: list[str] = []
        self._exporters: list = []

    def add_exporter(self, exporter):
        self._exporters.append(exporter)

    def start_span(
        self,
        name: str,
        attributes: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        span_id = uuid.uuid4().hex[:12]
        parent_span_id = self._active_spans[-1] if self._active_spans else ""

        if trace_id is None:
            if parent_span_id and parent_span_id in self._spans:
                trace_id = self._spans[parent_span_id].trace_id
            else:
                trace_id = uuid.uuid4().hex[:16]

        span = TraceSpan(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        self._spans[span_id] = span
        self._active_spans.append(span_id)
        logger.debug(f"Trace: started '{name}' ({span_id})")
        return span_id

    def end_span(self, span_id: str, status: str = "ok", error: str = ""):
        span = self._spans.get(span_id)
        if not span:
            logger.warning(f"Trace: unknown span {span_id}")
            return

        span.end_time = time.time()
        span.status = status
        span.error = error

        if self._active_spans and self._active_spans[-1] == span_id:
            self._active_spans.pop()

        self._export(span)
        logger.debug(f"Trace: ended '{span.name}' ({span.duration_ms:.1f}ms, {status})")

    def add_event(self, span_id: str, name: str, attributes: Optional[dict] = None):
        span = self._spans.get(span_id)
        if span:
            span.events.append({
                "name": name,
                "time": time.time(),
                "attributes": attributes or {},
            })

    def add_attributes(self, span_id: str, attributes: dict):
        span = self._spans.get(span_id)
        if span:
            span.attributes.update(attributes)

    def _export(self, span: TraceSpan):
        for exporter in self._exporters:
            try:
                exporter.export(span)
            except Exception as e:
                logger.warning(f"Trace export failed: {e}")

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return [s for s in self._spans.values() if s.trace_id == trace_id]

    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        return self._spans.get(span_id)

    def clear(self):
        self._spans.clear()
        self._active_spans.clear()

    @asynccontextmanager
    async def span(self, name: str, attributes: Optional[dict] = None):
        span_id = self.start_span(name, attributes)
        try:
            yield span_id
        except Exception as e:
            self.end_span(span_id, status="error", error=str(e))
            raise
        else:
            self.end_span(span_id)
