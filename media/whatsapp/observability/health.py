"""Health-check registry for the admin API's `/api/health` endpoint."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from media.whatsapp.observability.metrics import metrics


@dataclass
class _CheckResult:
    name: str
    healthy: bool
    message: str
    duration_ms: float
    timestamp: str


class HealthCheck:
    """Registry of health-check probes."""

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[[], tuple[bool, str]]] = {}
        self._lock = threading.Lock()
        self._last_results: List[_CheckResult] = []
        self._start_time = time.time()

    def register(self, name: str, fn: Callable[[], tuple[bool, str]]) -> None:
        """Register a health-check probe. `fn` returns (healthy, message)."""
        with self._lock:
            self._checks[name] = fn

    def run_all(self) -> dict:
        """Run all registered probes and return a JSON-serializable report."""
        results: List[_CheckResult] = []
        with self._lock:
            checks = list(self._checks.items())

        for name, fn in checks:
            start = time.time()
            try:
                healthy, message = fn()
            except Exception as e:
                healthy, message = False, f"probe error: {e}"
            duration_ms = (time.time() - start) * 1000
            results.append(_CheckResult(
                name=name,
                healthy=healthy,
                message=message,
                duration_ms=round(duration_ms, 2),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            ))

        self._last_results = results
        all_healthy = all(r.healthy for r in results) if results else False
        metrics.set("health_healthy", 1.0 if all_healthy else 0.0)
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "checks": [
                {
                    "name": r.name,
                    "healthy": r.healthy,
                    "message": r.message,
                    "duration_ms": r.duration_ms,
                    "timestamp": r.timestamp,
                }
                for r in results
            ],
        }


# Singleton
health = HealthCheck()
