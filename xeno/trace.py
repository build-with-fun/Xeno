"""Lightweight execution tracing — records LLM calls, tool calls, and agent handoffs.

Stores traces to data/traces/ as JSON files for later analysis.
Minimal overhead — no external dependencies."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    id: str = ""
    parent_id: str = ""
    name: str = ""
    span_type: str = ""  # llm_call | tool_call | handoff | task
    start_time: float = 0.0
    end_time: float = 0.0
    input: str = ""
    output: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
    children: list[TraceSpan] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > self.start_time else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_ms"] = self.duration_ms
        d["children"] = [c.to_dict() for c in self.children]
        return d


class Tracer:
    """Lightweight execution tracer. Usage:

    tracer = Tracer()
    with tracer.span("web_search", "tool_call", input={"query": "AI news"}):
        result = await web_search("AI news")
        tracer.current_span.output = str(result)
    """

    def __init__(self, trace_dir: str | Path = "data/traces"):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._root: Optional[TraceSpan] = None
        self._stack: list[TraceSpan] = []
        self._session_id = f"trace_{uuid.uuid4().hex[:12]}"

    @property
    def current_span(self) -> Optional[TraceSpan]:
        return self._stack[-1] if self._stack else None

    def start_span(self, name: str, span_type: str = "task", input: str = "", metadata: dict | None = None) -> TraceSpan:
        span = TraceSpan(
            id=uuid.uuid4().hex[:12],
            parent_id=self._stack[-1].id if self._stack else "",
            name=name,
            span_type=span_type,
            start_time=time.time(),
            input=input[:2000] if input else "",
            metadata=metadata or {},
        )
        if self._stack:
            self._stack[-1].children.append(span)
        else:
            self._root = span
        self._stack.append(span)
        return span

    def end_span(self, output: str = "", error: str = ""):
        if self._stack:
            span = self._stack.pop()
            span.end_time = time.time()
            if output:
                span.output = output[:2000]
            if error:
                span.error = error[:500]

    def span(self, name: str, span_type: str = "task", input: str = "", metadata: dict | None = None):
        return _SpanContext(self, name, span_type, input, metadata)

    def save(self) -> str:
        if self._root is None:
            return ""
        filename = f"{self._session_id}.json"
        path = self.trace_dir / filename
        data = {
            "session_id": self._session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "root": self._root.to_dict(),
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(path)

    def load(self, session_id: str) -> dict | None:
        path = self.trace_dir / f"{session_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def list_traces(self) -> list[dict]:
        traces = []
        for f in sorted(self.trace_dir.glob("*.json"), reverse=True)[:50]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                traces.append({"session_id": data.get("session_id", ""), "timestamp": data.get("timestamp", "")})
            except Exception:
                pass
        return traces


class _SpanContext:
    def __init__(self, tracer: Tracer, name: str, span_type: str, input: str, metadata: dict | None):
        self.tracer = tracer
        self.name = name
        self.span_type = span_type
        self.input = input
        self.metadata = metadata
        self.span: Optional[TraceSpan] = None

    def __enter__(self):
        self.span = self.tracer.start_span(self.name, self.span_type, self.input, self.metadata)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.tracer.end_span(error=str(exc_val))
        else:
            self.tracer.end_span()


# Global tracer instance
_TRACER: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _TRACER
    if _TRACER is None:
        _TRACER = Tracer()
    return _TRACER


def set_tracer(tracer: Tracer):
    global _TRACER
    _TRACER = tracer
