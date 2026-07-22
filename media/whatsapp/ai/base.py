"""Abstract AI provider interface and registry."""
from __future__ import annotations

import enum
import threading
import time
import hashlib
from typing import Any, Optional, Protocol

from media.whatsapp.core.exceptions import RateLimitError, AIProviderError
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)


class ProviderCapability(str, enum.Enum):
    TEXT = "text"
    VISION = "vision"
    JSON = "json"


class AIProvider(Protocol):
    """Protocol every AI provider must implement."""

    name: str
    capabilities: set[ProviderCapability]

    def is_available(self) -> bool: ...
    def is_on_cooldown(self) -> bool: ...
    def cooldown_remaining(self) -> float: ...

    def simple_text(self, prompt: str, max_chars: int) -> str: ...
    def structured_decision(
        self, system_prompt: str, user_content: str, max_chars: int,
    ) -> Optional[dict]: ...
    def reply(
        self, system_prompt: str, messages: list[dict],
        image_bytes: Optional[bytes], max_chars: int,
    ) -> str: ...


class AIRegistry:
    """Tracks per-key cooldowns in a thread-safe manner.

    Fixes the original code's `_api_cooldowns` dict which was mutated
    from multiple threads without a lock.
    """

    def __init__(self) -> None:
        self._cooldowns: dict[str, float] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _hash_key(key: str) -> str:
        # SHA-256 truncated to 16 hex chars — collision-resistant
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def is_on_cooldown(self, key: str) -> bool:
        h = self._hash_key(key)
        with self._lock:
            return time.time() < self._cooldowns.get(h, 0)

    def cooldown_remaining(self, key: str) -> float:
        h = self._hash_key(key)
        with self._lock:
            return max(0.0, self._cooldowns.get(h, 0) - time.time())

    def set_cooldown(self, key: str, seconds: int = 65) -> None:
        h = self._hash_key(key)
        with self._lock:
            self._cooldowns[h] = time.time() + seconds
        logger.warning(
            f"[RateLimit] Key {h} cooling down for {seconds}s",
            extra={"key_hash": h, "cooldown_secs": seconds},
        )

    def classify_error(self, err: Exception) -> bool:
        """Return True if the error indicates a rate limit (caller should set cooldown)."""
        msg = str(err).lower()
        return (
            "429" in msg or "quota" in msg or "rate limit" in msg
            or "resourceexhausted" in msg or "rate_limit_exceeded" in msg
        )


# Singleton
registry = AIRegistry()


def call_with_metrics(provider_name: str, fn):
    """Decorator-like wrapper: record metrics and re-raise as typed exceptions."""
    start = time.time()
    try:
        result = fn()
        metrics.observe("ai_latency_seconds", time.time() - start, provider=provider_name)
        metrics.inc("ai_calls_total", provider=provider_name, status="success")
        return result
    except Exception as e:
        metrics.inc("ai_calls_total", provider=provider_name, status="error")
        metrics.observe("ai_latency_seconds", time.time() - start, provider=provider_name)
        if registry.classify_error(e):
            raise RateLimitError(str(e), provider=provider_name) from e
        raise AIProviderError(str(e), provider=provider_name, transient=True) from e
