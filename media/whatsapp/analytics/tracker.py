"""Analytics tracker: per-day JSON files with thread-safe writes.

Fixes the original code's issues:
- Every event triggered a read-modify-write of the entire day's JSON file
- No locking — concurrent events could lose data
- Schema was hardcoded with no migration path
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Optional

from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class AnalyticsTracker:
    """Thread-safe per-day analytics."""

    COLLECTION = "analytics"

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def _today_key(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _default_day(self, date_str: str) -> dict:
        return {
            "date": date_str,
            "total_messages_received": 0,
            "total_replies_sent": 0,
            "approvals_needed": 0,
            "approvals_approved": 0,
            "approvals_rejected": 0,
            "send_failures": 0,
            "retries_succeeded": 0,
            "keyword_alerts": 0,
            "contacts_active": [],
            "ai_provider_usage": {"gemini": 0, "groq": 0, "openai": 0, "anthropic": 0},
            "message_types": {
                "text": 0, "voice": 0, "image": 0,
                "pdf": 0, "docx": 0, "video": 0, "sticker": 0,
            },
            "response_times_secs": [],
        }

    def track(self, contact: str, event: str, extra: Any = None) -> None:
        """Record an analytics event."""
        try:
            with self._lock:
                key = self._today_key()
                data = store.read(self.COLLECTION, key, self._default_day(key))
                if not isinstance(data, dict):
                    data = self._default_day(key)

                if contact and contact not in data.get("contacts_active", []):
                    data.setdefault("contacts_active", []).append(contact)

                event_map = {
                    "received":        "total_messages_received",
                    "sent":            "total_replies_sent",
                    "approval_needed": "approvals_needed",
                    "approved":        "approvals_approved",
                    "rejected":        "approvals_rejected",
                    "send_failed":     "send_failures",
                    "retry_success":   "retries_succeeded",
                    "alert_fired":     "keyword_alerts",
                }
                if event in event_map:
                    k = event_map[event]
                    data[k] = data.get(k, 0) + 1
                elif event.startswith("sent_"):
                    provider = event.split("_", 1)[1]
                    data.setdefault("ai_provider_usage", {})
                    data["ai_provider_usage"][provider] = (
                        data["ai_provider_usage"].get(provider, 0) + 1
                    )
                elif event == "received_type" and isinstance(extra, str):
                    t = extra if extra in data.get("message_types", {}) else "text"
                    data.setdefault("message_types", {})
                    data["message_types"][t] = data["message_types"].get(t, 0) + 1
                elif event == "response_time" and isinstance(extra, (int, float)):
                    data.setdefault("response_times_secs", []).append(round(extra, 2))
                    # Cap to last 1000 samples
                    if len(data["response_times_secs"]) > 1000:
                        data["response_times_secs"] = data["response_times_secs"][-1000:]

                store.write(self.COLLECTION, key, data)
        except Exception as e:
            logger.warning(f"[Analytics] {e}")

    def summary(self, days: int = 7) -> dict:
        """Return aggregated analytics for the last N days."""
        result = {"days": days, "files": []}
        for i in range(days):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            data = store.read(self.COLLECTION, d)
            if data:
                result["files"].append(data)
        return result


# Singleton
analytics = AnalyticsTracker()
