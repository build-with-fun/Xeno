from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_METRICS: Optional["MetricsCollector"] = None


def get_metrics() -> "MetricsCollector":
    global _METRICS
    if _METRICS is None:
        _METRICS = MetricsCollector()
    return _METRICS


@dataclass
class MetricPoint:
    timestamp: float = field(default_factory=time.time)
    value: float = 0.0
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    name: str
    points: list[MetricPoint] = field(default_factory=list)
    unit: str = "count"

    @property
    def last_value(self) -> float:
        return self.points[-1].value if self.points else 0.0

    @property
    def total(self) -> float:
        return sum(p.value for p in self.points)

    @property
    def average(self) -> float:
        return self.total / len(self.points) if self.points else 0.0


class MetricsCollector:
    """Collects and aggregates metrics about agent operations.

    Tracks:
    - Token usage per model/provider
    - Tool call latency and error rates
    - Task completion rates
    - Memory operation counts
    - Agent dispatch counts
    """

    def __init__(self):
        self._series: dict[str, MetricSeries] = defaultdict(lambda: MetricSeries(name=""))

    def record(self, name: str, value: float = 1.0, tags: Optional[dict[str, str]] = None):
        if name not in self._series:
            self._series[name] = MetricSeries(name=name)
        self._series[name].points.append(MetricPoint(value=value, tags=tags or {}))

    def record_tokens(self, model: str, input_tokens: int, output_tokens: int):
        self.record(f"token.input.{model}", input_tokens)
        self.record(f"token.output.{model}", output_tokens)
        self.record(f"token.total.{model}", input_tokens + output_tokens)

    def record_tool_call(self, tool_name: str, duration_ms: float, success: bool = True):
        self.record(f"tool.{tool_name}.calls", 1.0)
        self.record(f"tool.{tool_name}.latency_ms", duration_ms)
        if not success:
            self.record(f"tool.{tool_name}.errors", 1.0)
        self.record("tool.total.calls", 1.0)
        self.record("tool.total.latency_ms", duration_ms)

    def record_task(self, task_type: str, duration_s: float, success: bool = True):
        self.record(f"task.{task_type}.count", 1.0)
        self.record(f"task.{task_type}.duration_s", duration_s)
        if not success:
            self.record(f"task.{task_type}.errors", 1.0)

    def record_memory_op(self, op: str, tier: str):
        self.record(f"memory.{op}.{tier}", 1.0)

    def get_series(self, name: str) -> Optional[MetricSeries]:
        return self._series.get(name)

    def summary(self) -> dict:
        result = {}
        for name, series in self._series.items():
            result[name] = {
                "count": len(series.points),
                "last": series.last_value,
                "total": series.total,
                "avg": series.average,
            }
        return result

    def save(self, path: str | Path):
        data = {}
        for name, series in self._series.items():
            data[name] = {
                "name": name,
                "unit": series.unit,
                "points": [(p.timestamp, p.value, p.tags) for p in series.points[-1000:]],
            }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str | Path):
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text())
            for name, sdata in data.items():
                series = MetricSeries(name=sdata["name"], unit=sdata.get("unit", "count"))
                for ts, val, tags in sdata.get("points", []):
                    series.points.append(MetricPoint(timestamp=ts, value=val, tags=tags))
                self._series[name] = series

    def clear(self):
        self._series.clear()
