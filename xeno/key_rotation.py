"""Key rotation system for API keys.

Manages multiple keys per provider with health tracking,
failover, and multiple rotation strategies. Thread-safe.

Strategies:
- round_robin: cycle through keys in order
- random: pick a random healthy key
- least_used: pick the key with fewest requests
- fastest: pick the key with lowest avg latency
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

logger = logging.getLogger("xeno.key_rotation")

KEY_STATS_FILE = Path(__file__).parent.parent / "data" / "key_stats.json"


@dataclass
class KeyHealth:
    key: str
    provider: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    rate_limited: int = 0
    total_latency_ms: float = 0.0
    last_used: float = 0.0
    last_error: float = 0.0
    last_error_msg: str = ""
    consecutive_failures: int = 0
    is_healthy: bool = True
    cooldown_until: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful == 0:
            return 99999.0
        return self.total_latency_ms / self.successful

    @property
    def masked(self) -> str:
        if len(self.key) <= 12:
            return self.key[:4] + "..." + self.key[-3:]
        return self.key[:8] + "..." + self.key[-4:]

    def record_success(self, latency_ms: float):
        self.total_requests += 1
        self.successful += 1
        self.total_latency_ms += latency_ms
        self.last_used = time.time()
        self.consecutive_failures = 0
        self.is_healthy = True
        self.cooldown_until = 0.0

    def record_failure(self, error_msg: str = "", is_rate_limit: bool = False):
        self.total_requests += 1
        self.failed += 1
        self.last_error = time.time()
        self.last_error_msg = error_msg
        self.consecutive_failures += 1
        if is_rate_limit:
            self.rate_limited += 1
            # Cool down for 60s on rate limit
            self.cooldown_until = time.time() + 60.0
        # Mark unhealthy after 5 consecutive failures
        if self.consecutive_failures >= 5:
            self.is_healthy = False
            logger.warning(f"Key {self.masked} marked unhealthy after {self.consecutive_failures} failures")

    @property
    def is_available(self) -> bool:
        if not self.is_healthy:
            return False
        if time.time() < self.cooldown_until:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "key": self.masked,
            "provider": self.provider,
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "success_rate": round(self.success_rate, 3),
            "is_healthy": self.is_healthy,
            "is_available": self.is_available,
            "consecutive_failures": self.consecutive_failures,
        }


class KeyRotationManager:
    """Thread-safe key rotation manager."""

    def __init__(
        self,
        strategy: str = "round_robin",
        max_retries: int = 3,
        rate_limit_backoff: float = 60.0,
    ):
        self.strategy = strategy
        self.max_retries = max_retries
        self.rate_limit_backoff = rate_limit_backoff
        self._keys: dict[str, list[KeyHealth]] = {}  # provider -> keys
        self._index: dict[str, int] = {}  # provider -> round_robin index
        self._lock = threading.Lock()
        self._load_stats()

    def _load_stats(self):
        if KEY_STATS_FILE.exists():
            try:
                data = json.loads(KEY_STATS_FILE.read_text())
                for provider, keys_data in data.items():
                    self._keys[provider] = []
                    for kd in keys_data:
                        kh = KeyHealth(
                            key=kd.get("raw_key", kd.get("key", "")),
                            provider=provider,
                            total_requests=kd.get("total_requests", 0),
                            successful=kd.get("successful", 0),
                            failed=kd.get("failed", 0),
                            rate_limited=kd.get("rate_limited", 0),
                            total_latency_ms=kd.get("total_latency_ms", 0),
                            consecutive_failures=kd.get("consecutive_failures", 0),
                            is_healthy=kd.get("is_healthy", True),
                        )
                        self._keys[provider].append(kh)
            except Exception as e:
                logger.debug(f"Failed to load key stats: {e}")

    def _save_stats(self):
        data = {}
        for provider, keys in self._keys.items():
            data[provider] = []
            for kh in keys:
                entry = kh.to_dict()
                entry["raw_key"] = kh.key  # save for reload
                data[provider].append(entry)
        KEY_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_STATS_FILE.write_text(json.dumps(data, indent=2))

    def register_provider(self, provider: str, keys: list[str]):
        """Register keys for a provider."""
        with self._lock:
            existing_keys = {kh.key for kh in self._keys.get(provider, [])}
            new_healths = []
            for key in keys:
                if key in existing_keys:
                    # Find existing and keep stats
                    for kh in self._keys.get(provider, []):
                        if kh.key == key:
                            new_healths.append(kh)
                            break
                else:
                    new_healths.append(KeyHealth(key=key, provider=provider))
            self._keys[provider] = new_healths
            if provider not in self._index:
                self._index[provider] = 0
            self._save_stats()

    def get_key(self, provider: str) -> str:
        """Get the next key for a provider using the configured strategy."""
        with self._lock:
            keys = self._keys.get(provider, [])
            if not keys:
                # Fallback: scan env
                self._auto_discover(provider)
                keys = self._keys.get(provider, [])
            if not keys:
                raise ValueError(f"No API keys registered for provider: {provider}")

            available = [kh for kh in keys if kh.is_available]
            if not available:
                # All keys exhausted — reset cooldowns and try again
                logger.warning(f"All keys for {provider} exhausted, resetting cooldowns")
                for kh in keys:
                    kh.cooldown_until = 0.0
                    kh.is_healthy = True
                    kh.consecutive_failures = 0
                available = keys

            if self.strategy == "round_robin":
                idx = self._index.get(provider, 0) % len(available)
                self._index[provider] = idx + 1
                return available[idx].key
            elif self.strategy == "random":
                return random.choice(available).key
            elif self.strategy == "least_used":
                return min(available, key=lambda kh: kh.total_requests).key
            elif self.strategy == "fastest":
                return min(available, key=lambda kh: kh.avg_latency_ms).key
            else:
                return available[0].key

    def record_success(self, provider: str, key: str, latency_ms: float):
        """Record a successful request."""
        with self._lock:
            for kh in self._keys.get(provider, []):
                if kh.key == key:
                    kh.record_success(latency_ms)
                    break
            self._save_stats()

    def record_failure(self, provider: str, key: str, error: str = "", is_rate_limit: bool = False):
        """Record a failed request."""
        with self._lock:
            for kh in self._keys.get(provider, []):
                if kh.key == key:
                    kh.record_failure(error, is_rate_limit)
                    break
            self._save_stats()

    def get_stats(self, provider: Optional[str] = None) -> dict[str, Any]:
        """Get key health stats."""
        with self._lock:
            result = {}
            providers = [provider] if provider else list(self._keys.keys())
            for p in providers:
                keys = self._keys.get(p, [])
                result[p] = {
                    "strategy": self.strategy,
                    "total_keys": len(keys),
                    "healthy_keys": sum(1 for kh in keys if kh.is_available),
                    "keys": [kh.to_dict() for kh in keys],
                }
            return result

    def reset_key(self, provider: str, key_mask: str):
        """Reset a specific key's health."""
        with self._lock:
            for kh in self._keys.get(provider, []):
                if kh.masked == key_mask:
                    kh.consecutive_failures = 0
                    kh.is_healthy = True
                    kh.cooldown_until = 0.0
                    break
            self._save_stats()

    def reset_all(self, provider: Optional[str] = None):
        """Reset all keys health."""
        with self._lock:
            providers = [provider] if provider else list(self._keys.keys())
            for p in providers:
                for kh in self._keys.get(p, []):
                    kh.consecutive_failures = 0
                    kh.is_healthy = True
                    kh.cooldown_until = 0.0
            self._save_stats()

    def _auto_discover(self, provider: str):
        """Auto-discover keys from env."""
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)
        env_patterns = {
            "gemini": [r"^GEMINI_API_KEY", r"^GOOGLE_API_KEY"],
            "deepseek": [r"^DEEPSEEK_API_KEY"],
            "groq": [r"^GROQ_API_KEY"],
            "openai": [r"^OPENAI_API_KEY"],
            "anthropic": [r"^ANTHROPIC_API_KEY"],
            "qwen": [r"^QWEN_API_KEY"],
            "ollama": [],
        }
        import re
        patterns = env_patterns.get(provider, [])
        keys = []
        for env_key, value in os.environ.items():
            for pattern in patterns:
                if re.match(pattern, env_key, re.IGNORECASE) and value.strip():
                    keys.append(value.strip())
        if keys:
            self.register_provider(provider, keys)

    def set_strategy(self, strategy: str):
        """Change rotation strategy."""
        valid = {"round_robin", "random", "least_used", "fastest"}
        if strategy not in valid:
            raise ValueError(f"Invalid strategy: {strategy}. Must be one of: {valid}")
        self.strategy = strategy
        logger.info(f"Rotation strategy changed to: {strategy}")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_manager: Optional[KeyRotationManager] = None


def get_key_manager() -> KeyRotationManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = KeyRotationManager()
    return _global_manager


def init_key_manager(
    provider: str,
    keys: list[str],
    strategy: str = "round_robin",
    max_retries: int = 3,
) -> KeyRotationManager:
    """Initialize the global key manager with setup config."""
    global _global_manager
    _global_manager = KeyRotationManager(
        strategy=strategy,
        max_retries=max_retries,
    )
    _global_manager.register_provider(provider, keys)
    logger.info(f"Key manager initialized: {provider}, {len(keys)} keys, strategy={strategy}")
    return _global_manager
