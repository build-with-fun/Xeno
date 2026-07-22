"""Message scheduler manager.

Runs as a background thread, checking for due scheduled messages every
few seconds and sending them via the browser sender.
"""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)


class SchedulerManager:
    """Background scheduler for delayed/recurring message sending."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._page_lock: Optional[threading.RLock] = None
        self._page_ref: Optional[list] = None
        self._interval = 5  # Check every 5 seconds

    def start(self, page_ref: list, page_lock: threading.RLock) -> None:
        """Start the scheduler thread."""
        self._page_ref = page_ref
        self._page_lock = page_lock
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="scheduler", daemon=True,
        )
        self._thread.start()
        logger.info("[Scheduler] Started — checking every 5s")

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        self._stop_event.set()

    def schedule(self, contact_name: str, text: str,
                 scheduled_for: datetime, recurrence: str = None) -> int:
        """Schedule a message. Returns the scheduled message ID."""
        from media.whatsapp.db.repo import ScheduledMessageRepo
        msg = ScheduledMessageRepo.schedule(contact_name, text, scheduled_for, recurrence)
        logger.info(
            f"[Scheduler] Scheduled message to {contact_name} "
            f"for {scheduled_for.isoformat()}"
            + (f" (recurs {recurrence})" if recurrence else "")
        )
        return msg.id

    def cancel(self, msg_id: int) -> bool:
        """Cancel a scheduled message."""
        from media.whatsapp.db.repo import ScheduledMessageRepo
        ok = ScheduledMessageRepo.cancel(msg_id)
        if ok:
            logger.info(f"[Scheduler] Cancelled message {msg_id}")
        return ok

    def list_pending(self) -> list:
        """List all pending scheduled messages."""
        from media.whatsapp.db.repo import ScheduledMessageRepo
        return ScheduledMessageRepo.list_pending()

    def _loop(self) -> None:
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                self._process_due()
            except Exception as e:
                logger.error(f"[Scheduler] Loop error: {e}\n{traceback.format_exc()}")
            self._stop_event.wait(self._interval)

    def _process_due(self) -> None:
        """Send all due scheduled messages."""
        from media.whatsapp.db.repo import ScheduledMessageRepo

        due = ScheduledMessageRepo.get_due()
        if not due:
            return

        page = self._page_ref[0] if self._page_ref else None
        if page is None:
            logger.warning("[Scheduler] No browser page — skipping")
            return

        from media.whatsapp.browser.navigation import navigation
        from media.whatsapp.browser.sender import sender
        from media.whatsapp.human.behavior import human

        for msg in due:
            if self._stop_event.is_set():
                return
            try:
                with self._page_lock:
                    if not navigation.open_chat(page, msg.contact_name):
                        logger.warning(
                            f"[Scheduler] Could not open chat for {msg.contact_name}"
                        )
                        continue
                    sent = sender.send(page, msg.text)
                    navigation.close_chat(page)

                if sent:
                    ScheduledMessageRepo.mark_sent(msg.id)
                    metrics.inc("scheduled_sent")
                    logger.info(
                        f"[Scheduler] Sent scheduled message to {msg.contact_name}"
                    )
                else:
                    logger.warning(
                        f"[Scheduler] Send failed for {msg.contact_name}"
                    )
            except Exception as e:
                logger.error(f"[Scheduler] Error sending to {msg.contact_name}: {e}")


# Singleton
scheduler = SchedulerManager()
