"""Broadcast campaign manager.

Sends personalized messages to multiple contacts with rate limiting
and progress tracking. Respects per-contact rate limits and anti-detection
delays.

Usage:
    broadcast_manager.create_campaign(
        name="Diwali Greetings",
        template="Hi {name}, wishing you a happy Diwali! 🎉",
        recipients=["Alice", "Bob", "Charlie"],
        variables={"Alice": {"name": "Alice"}, "Bob": {"name": "Bobby"}},
    )
    broadcast_manager.start_campaign(campaign_id)
"""
from __future__ import annotations

import random
import threading
import time
import traceback
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)


class BroadcastManager:
    """Manages broadcast campaigns with rate-limited sending."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._page_lock: Optional[threading.RLock] = None
        self._page_ref: Optional[list] = None
        self._running_campaigns: set[int] = set()
        self._lock = threading.RLock()

    def start(self, page_ref: list, page_lock: threading.RLock) -> None:
        """Start the broadcast worker thread."""
        self._page_ref = page_ref
        self._page_lock = page_lock
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="broadcast-worker", daemon=True,
        )
        self._thread.start()
        logger.info("[Broadcast] Worker started")

    def stop(self) -> None:
        """Signal the broadcast worker to stop."""
        self._stop_event.set()

    def create_campaign(
        self, name: str, template: str, recipients: list[str],
        variables: dict = None,
    ) -> int:
        """Create a new broadcast campaign. Returns campaign ID."""
        from media.whatsapp.db.repo import BroadcastRepo
        campaign = BroadcastRepo.create_campaign(name, template, recipients, variables)
        logger.info(
            f"[Broadcast] Created campaign '{name}' with {len(recipients)} recipients"
        )
        return campaign.id

    def start_campaign(self, campaign_id: int) -> bool:
        """Mark a campaign as ready to run."""
        from media.whatsapp.db.repo import BroadcastRepo
        from media.whatsapp.db.models import CampaignStatus
        with self._lock:
            self._running_campaigns.add(campaign_id)
        BroadcastRepo.update_campaign_status(campaign_id, CampaignStatus.RUNNING)
        logger.info(f"[Broadcast] Started campaign {campaign_id}")
        return True

    def pause_campaign(self, campaign_id: int) -> bool:
        """Pause a running campaign."""
        from media.whatsapp.db.repo import BroadcastRepo
        from media.whatsapp.db.models import CampaignStatus
        with self._lock:
            self._running_campaigns.discard(campaign_id)
        BroadcastRepo.update_campaign_status(campaign_id, CampaignStatus.PAUSED)
        return True

    def cancel_campaign(self, campaign_id: int) -> bool:
        """Cancel a campaign."""
        from media.whatsapp.db.repo import BroadcastRepo
        from media.whatsapp.db.models import CampaignStatus
        with self._lock:
            self._running_campaigns.discard(campaign_id)
        BroadcastRepo.update_campaign_status(campaign_id, CampaignStatus.CANCELLED)
        return True

    def list_campaigns(self) -> list:
        """List all campaigns."""
        from media.whatsapp.db.repo import BroadcastRepo
        return [c for c in BroadcastRepo.list_campaigns()]

    def get_campaign(self, campaign_id: int) -> Optional[dict]:
        """Get a campaign by ID."""
        from media.whatsapp.db.repo import BroadcastRepo
        c = BroadcastRepo.get(campaign_id)
        return c

    def _loop(self) -> None:
        """Main broadcast worker loop."""
        while not self._stop_event.is_set():
            try:
                self._process_campaigns()
            except Exception as e:
                logger.error(f"[Broadcast] Loop error: {e}\n{traceback.format_exc()}")
            self._stop_event.wait(10)  # Check every 10 seconds

    def _process_campaigns(self) -> None:
        """Process all running campaigns."""
        with self._lock:
            campaign_ids = list(self._running_campaigns)

        if not campaign_ids:
            return

        from media.whatsapp.db.repo import BroadcastRepo
        from media.whatsapp.db.models import CampaignStatus

        for campaign_id in campaign_ids:
            if self._stop_event.is_set():
                return
            try:
                recipients = BroadcastRepo.get_pending_recipients(campaign_id)
                if not recipients:
                    # Campaign complete
                    with self._lock:
                        self._running_campaigns.discard(campaign_id)
                    BroadcastRepo.update_campaign_status(campaign_id, CampaignStatus.COMPLETED)
                    logger.info(f"[Broadcast] Campaign {campaign_id} completed")
                    continue

                # Send to one recipient per cycle (rate-limited)
                page = self._page_ref[0] if self._page_ref else None
                if page is None:
                    continue

                from media.whatsapp.browser.navigation import navigation
                from media.whatsapp.browser.sender import sender
                from media.whatsapp.human.behavior import human
                from media.whatsapp.safety.rate_limiter import rate_limiter

                for r in recipients:
                    if self._stop_event.is_set():
                        return
                    # Check rate limit
                    if not rate_limiter.can_reply(r.contact_name):
                        logger.info(
                            f"[Broadcast] {r.contact_name} rate-limited, skipping"
                        )
                        continue

                    try:
                        with self._page_lock:
                            if not navigation.open_chat(page, r.contact_name):
                                BroadcastRepo.mark_recipient_failed(
                                    r.id, "Could not open chat"
                                )
                                continue
                            sent = sender.send(page, r.personalized_text)
                            navigation.close_chat(page)

                        if sent:
                            BroadcastRepo.mark_recipient_sent(r.id)
                            rate_limiter.record_reply(r.contact_name)
                            metrics.inc("broadcast_sent")
                            # Anti-detection delay between sends
                            delay = random.uniform(
                                settings.reply_delay_min * 2,
                                settings.reply_delay_max * 3,
                            )
                            time.sleep(delay)
                        else:
                            BroadcastRepo.mark_recipient_failed(r.id, "Send failed")
                    except Exception as e:
                        logger.error(f"[Broadcast] Error for {r.contact_name}: {e}")
                        BroadcastRepo.mark_recipient_failed(r.id, str(e))
            except Exception as e:
                logger.error(f"[Broadcast] Campaign {campaign_id} error: {e}")


# Singleton
broadcast_manager = BroadcastManager()
