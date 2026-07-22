"""Production hardening — budgets, cost, circuit breaker, metrics, telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class TokenBudget:
    total: int
    used: int = 0
    reserved: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used - self.reserved)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


class BudgetManager:
    def __init__(self, default_session: int = 200_000, default_task: int = 10_000):
        self.default_session = default_session
        self.default_task = default_task
        self._sessions: dict[str, TokenBudget] = {}

    def create_session_budget(self, sid: str, total: Optional[int] = None) -> TokenBudget:
        b = TokenBudget(total or self.default_session)
        self._sessions[sid] = b
        return b

    def can_spend(self, sid: str, amount: int) -> bool:
        b = self._sessions.get(sid)
        return b is not None and not b.exhausted and b.remaining >= amount

    def stats(self) -> dict:
        return {"sessions": len(self._sessions)}


MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-v4-flash": {"input": 0.10, "output": 0.40},
    "deepseek-v4-pro": {"input": 0.50, "output": 1.80},
    "glm-4.6": {"input": 0.60, "output": 2.20},
    "glm-5": {"input": 1.00, "output": 3.50},
    "default": {"input": 1.00, "output": 3.00},
}


@dataclass
class CostEntry:
    id: str
    timestamp: float
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    session_id: str = ""


class CostTracker:
    def __init__(self, log_path: Optional[Path] = None, pricing: Optional[dict] = None):
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        self.pricing = pricing or MODEL_PRICING
        self._entries: list[CostEntry] = []

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        session_id: str = "",
    ) -> CostEntry:
        p = self.pricing.get(model, self.pricing["default"])
        cost = (input_tokens / 1e6 * p["input"]) + (output_tokens / 1e6 * p["output"])
        e = CostEntry(
            id=f"cost_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            session_id=session_id,
        )
        self._entries.append(e)
        if self.log_path:
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(e)) + "\n")
            except Exception:
                pass
        return e

    def stats(self) -> dict:
        if not self._entries:
            return {"total_cost": 0, "total_calls": 0}
        total = sum(e.cost_usd for e in self._entries)
        return {"total_cost": round(total, 4), "total_calls": len(self._entries)}

    def cost_today(self) -> float:
        cutoff = time.time() - 86400
        return round(sum(e.cost_usd for e in self._entries if e.timestamp >= cutoff), 4)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._state: dict[str, CircuitState] = {}
        self._failures: dict[str, int] = defaultdict(int)
        self._last_failure: dict[str, float] = {}

    def can_call(self, model: str) -> bool:
        state = self._state.get(model, CircuitState.CLOSED)
        if state == CircuitState.OPEN:
            if time.time() - self._last_failure.get(model, 0) > self.cooldown:
                self._state[model] = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self, model: str) -> None:
        self._failures[model] = 0
        self._state[model] = CircuitState.CLOSED

    def record_failure(self, model: str) -> None:
        self._failures[model] += 1
        self._last_failure[model] = time.time()
        if self._failures[model] >= self.failure_threshold:
            self._state[model] = CircuitState.OPEN
            logger.warning(f"Circuit OPEN for {model} after {self._failures[model]} failures")

    def get_state(self, model: str) -> CircuitState:
        return self._state.get(model, CircuitState.CLOSED)


class ModelFallbackChain:
    def __init__(self, models: list[str], circuit: Optional[CircuitBreaker] = None):
        self.models = models
        self.circuit = circuit or CircuitBreaker()

    async def call(self, call_fn: Callable[[str], Awaitable[Any]]) -> tuple[Any, str]:
        last_error = None
        for model in self.models:
            if not self.circuit.can_call(model):
                continue
            try:
                result = await call_fn(model)
                self.circuit.record_success(model)
                return result, model
            except Exception as e:
                last_error = e
                self.circuit.record_failure(model)
                logger.warning(f"Model {model} failed: {e}. Trying fallback...")
        raise RuntimeError(f"All models failed. Last error: {last_error}")


class TokenBucketRateLimiter:
    def __init__(self, rate: float = 10.0, burst: int = 20):
        self.rate = rate
        self.burst = burst
        self._buckets: dict[str, dict] = {}

    def try_consume(self, key: str, amount: int = 1) -> bool:
        now = time.time()
        b = self._buckets.setdefault(key, {"tokens": float(self.burst), "last": now})
        b["tokens"] = min(self.burst, b["tokens"] + (now - b["last"]) * self.rate)
        b["last"] = now
        if b["tokens"] >= amount:
            b["tokens"] -= amount
            return True
        return False


class MetricsCollector:
    def __init__(self, namespace: str = "xeno"):
        self.namespace = namespace
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}

    def inc_counter(self, name: str, value: int = 1, labels: Optional[dict] = None) -> None:
        k = f"{name}:{labels or {}}"
        self._counters[k] = self._counters.get(k, 0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[dict] = None) -> None:
        k = f"{name}:{labels or {}}"
        self._gauges[k] = value

    def stats(self) -> dict:
        return {"counters": len(self._counters), "gauges": len(self._gauges)}


class TelemetryTracer:
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        self._spans: list[dict] = []

    def start_span(
        self,
        name: str,
        parent_id: str = "",
        trace_id: Optional[str] = None,
        attributes: Optional[dict] = None,
    ):
        @dataclass
        class Span:
            id: str
            trace_id: str
            parent_id: str
            name: str
            start_time: float = field(default_factory=time.time)
            end_time: float = 0
            attributes: dict = field(default_factory=dict)

        s = Span(
            id=f"span_{uuid.uuid4().hex[:12]}",
            trace_id=trace_id or f"trace_{uuid.uuid4().hex[:16]}",
            parent_id=parent_id,
            name=name,
            attributes=attributes or {},
        )
        return s

    def end_span(self, span, status: str = "ok", error: str = "") -> None:
        span.end_time = time.time()
        span_dict = {
            "id": span.id,
            "trace_id": span.trace_id,
            "name": span.name,
            "duration_ms": int((span.end_time - span.start_time) * 1000),
            "status": status,
            "error": error,
        }
        self._spans.append(span_dict)
        if self.log_path:
            try:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(span_dict) + "\n")
            except Exception:
                pass

    def stats(self) -> dict:
        return {"total_spans": len(self._spans)}


class ProductionBundle:
    """Convenience: bundles all production subsystems together."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.budget = BudgetManager()
        self.cost = CostTracker(log_path=data_dir / "costs.jsonl")
        self.circuit = CircuitBreaker()
        self.rate_limiter = TokenBucketRateLimiter()
        self.metrics = MetricsCollector()
        self.telemetry = TelemetryTracer(log_path=data_dir / "traces.jsonl")

    async def startup(self) -> None:
        logger.info("Production bundle started")

    async def shutdown(self) -> None:
        logger.info("Production bundle shutdown")

    def status(self) -> dict:
        return {
            "cost_today": self.cost.cost_today(),
            "cost_stats": self.cost.stats(),
            "budget": self.budget.stats(),
            "metrics": self.metrics.stats(),
        }
