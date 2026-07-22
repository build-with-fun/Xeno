"""Thread-safe in-memory metrics counters.

A lightweight alternative to Prometheus. Counters and gauges are tracked in
memory and exposed via the admin API at `/api/metrics`.

Fixes the original code's issues:
- Analytics were stored in per-day JSON files, requiring disk I/O on every event
- No counters for AI provider usage, errors, queue sizes, etc.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class _MetricValue:
    counters: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    gauges: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    histograms: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))


class Metrics:
    """Thread-safe metrics registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data = _MetricValue()
        self._start_time = time.time()

    # ── Counters ─────────────────────────────────────────────────────────────
    def inc(self, name: str, value: float = 1.0, **tags) -> None:
        """Increment a counter. Tags are flattened into the key."""
        key = self._key(name, tags)
        with self._lock:
            self._data.counters[key] += value

    # ── Gauges ───────────────────────────────────────────────────────────────
    def set(self, name: str, value: float, **tags) -> None:
        key = self._key(name, tags)
        with self._lock:
            self._data.gauges[key] = value

    def get(self, name: str, **tags) -> float:
        key = self._key(name, tags)
        with self._lock:
            return self._data.gauges.get(key, 0.0)

    # ── Histograms (for latency distributions) ───────────────────────────────
    def observe(self, name: str, value: float, **tags) -> None:
        key = self._key(name, tags)
        with self._lock:
            samples = self._data.histograms[key]
            samples.append(value)
            # Keep last 1000 samples per metric
            if len(samples) > 1000:
                del samples[:100]

    # ── Snapshot ─────────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of all metrics."""
        with self._lock:
            counters = dict(self._data.counters)
            gauges = dict(self._data.gauges)
            histograms = {}
            for k, samples in self._data.histograms.items():
                if not samples:
                    continue
                sorted_s = sorted(samples)
                n = len(sorted_s)
                histograms[k] = {
                    "count": n,
                    "sum": round(sum(sorted_s), 3),
                    "avg": round(sum(sorted_s) / n, 3),
                    "p50": round(sorted_s[n // 2], 3),
                    "p95": round(sorted_s[min(n - 1, int(n * 0.95))], 3),
                    "p99": round(sorted_s[min(n - 1, int(n * 0.99))], 3),
                    "min": round(sorted_s[0], 3),
                    "max": round(sorted_s[-1], 3),
                }
            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
            }

    # ── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _key(name: str, tags: dict) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"


# Singleton
metrics = Metrics()
