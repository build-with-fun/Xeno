"""Circuit breaker: auto-pause the bot on cascading failures.

When the bot experiences too many consecutive errors (send failures,
AI errors, browser crashes), the circuit "trips" and automatically
pauses message processing. This prevents a cascading failure from
flood-retrying and making things worse.

States:
  - CLOSED: Normal operation. Failures counted.
  - OPEN: Paused. All operations blocked. Waits for cooldown.
  - HALF_OPEN: Testing. One operation allowed; if it succeeds, CLOSE.
"""
from __future__ import annotations

import enum
import threading
import time
from typing import Optional

from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 10,
        cooldown_secs: int = 60,
        success_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_secs = cooldown_secs
        self.success_threshold = success_threshold
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float = 0.0
        self._last_error: str = ""

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if cooldown has elapsed
                if time.time() - self._opened_at >= self.cooldown_secs:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("[CircuitBreaker] OPEN → HALF_OPEN (testing)")
            return self._state

    def can_proceed(self) -> bool:
        """Return True if operations are allowed."""
        state = self.state
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("[CircuitBreaker] HALF_OPEN → CLOSED (recovered)")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self, error: str = "") -> None:
        """Record a failed operation."""
        with self._lock:
            self._last_error = error
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN:
                # Failure during testing — re-open
                self._trip()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._trip()

    def _trip(self) -> None:
        """Trip the circuit to OPEN."""
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        logger.error(
            f"[CircuitBreaker] TRIPPED — pausing for {self.cooldown_secs}s "
            f"(failures={self._failure_count}, last_error={self._last_error[:100]})"
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_error = ""
            logger.info("[CircuitBreaker] Manually reset")

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "cooldown_secs": self.cooldown_secs,
                "last_error": self._last_error[:200],
                "opened_at": self._opened_at,
                "cooldown_remaining": max(
                    0, self.cooldown_secs - (time.time() - self._opened_at)
                ) if self._state == CircuitState.OPEN else 0,
            }


# Singleton — global circuit breaker for the bot
circuit_breaker = CircuitBreaker(
    failure_threshold=10,
    cooldown_secs=60,
    success_threshold=3,
)
