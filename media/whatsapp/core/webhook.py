"""Enhanced two-way webhook system.

Sends events to configured webhook URLs with:
  - HMAC signature verification
  - Retry with exponential backoff
  - Event filtering (only send specific event types)
  - Dead-letter queue for failed webhooks

Supported events:
  - message_received: A new incoming message
  - message_sent: A reply was sent
  - approval_needed: A message needs human approval
  - approval_processed: An approval was approved/rejected
  - keyword_alert: A keyword was detected
  - spam_detected: Spam was detected
  - sentiment_alert: Angry sentiment detected
  - bot_started / bot_stopped: Bot lifecycle
  - error: Any error
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

import requests

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.utils.crypto import hmac_sign

logger = get_logger(__name__)


class EnhancedWebhook:
    """Two-way webhook with retries and dead-letter queue."""

    def __init__(self) -> None:
        self._url = settings.webhook_url
        self._secret = settings.webhook_secret
        self._lock = threading.RLock()
        self._dead_letter: deque[dict] = deque(maxlen=100)
        self._retry_delays = [0, 5, 30, 120, 600]  # seconds
        # Event types to send (empty = all)
        self._enabled_events: set[str] = set()

    def configure(
        self, url: str = None, secret: str = None,
        enabled_events: list[str] = None,
    ) -> None:
        """Update webhook configuration."""
        if url is not None:
            self._url = url
        if secret is not None:
            self._secret = secret
        if enabled_events is not None:
            self._enabled_events = set(enabled_events)

    def fire(self, event_type: str, data: dict) -> None:
        """Fire a webhook event (non-blocking)."""
        if not self._url:
            return
        # Filter by enabled events
        if self._enabled_events and event_type not in self._enabled_events:
            return

        payload = json.dumps({
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }, default=str)

        thread = threading.Thread(
            target=self._send_with_retry, args=(payload,), daemon=True,
        )
        thread.start()

    def _send_with_retry(self, payload: str) -> None:
        """Send payload with exponential backoff retry."""
        for attempt, delay in enumerate(self._retry_delays):
            if delay > 0:
                time.sleep(delay)
            try:
                headers = {"Content-Type": "application/json"}
                if self._secret:
                    sig = hmac_sign(self._secret, payload)
                    headers["X-Signature"] = sig
                r = requests.post(
                    self._url, data=payload, headers=headers, timeout=10,
                )
                if r.ok:
                    return  # Success
                logger.warning(
                    f"[Webhook] Attempt {attempt+1}: HTTP {r.status_code}"
                )
            except Exception as e:
                logger.warning(f"[Webhook] Attempt {attempt+1}: {e}")

        # All retries failed — add to dead letter queue
        with self._lock:
            self._dead_letter.append({
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
                "attempts": len(self._retry_delays),
            })
        logger.error(f"[Webhook] All retries failed — added to dead letter queue")

    def get_dead_letter(self, limit: int = 50) -> list[dict]:
        """Return dead-letter entries."""
        with self._lock:
            return list(self._dead_letter)[-limit:]

    def clear_dead_letter(self) -> int:
        """Clear the dead-letter queue. Returns count cleared."""
        with self._lock:
            count = len(self._dead_letter)
            self._dead_letter.clear()
            return count


# Singleton
webhook = EnhancedWebhook()
