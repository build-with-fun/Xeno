"""Background worker threads for processing approval & retry queues."""
from __future__ import annotations

import threading
import time
import traceback
from typing import Optional

from media.whatsapp.browser.navigation import navigation
from media.whatsapp.browser.sender import sender
from media.whatsapp.config import settings
from media.whatsapp.core.types import ApprovalItem
from media.whatsapp.human.behavior import human
from media.whatsapp.memory.history import history_manager
from media.whatsapp.memory.personas import persona_manager
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.taskqueue.approval import approval_queue
from media.whatsapp.taskqueue.retry import retry_queue

logger = get_logger(__name__)


class QueueWorker:
    """Runs the approval-sender and retry-sender daemon threads.

    Both workers share a single browser page; coordination is via the
    `_page_lock` (held during send operations) and per-item locks inside
    the queues themselves.
    """

    def __init__(self) -> None:
        self._page_lock: Optional[threading.RLock] = None
        self._stop_event = threading.Event()
        self._approval_thread: Optional[threading.Thread] = None
        self._retry_thread: Optional[threading.Thread] = None

    @property
    def page_lock(self) -> Optional[threading.RLock]:
        return self._page_lock

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def start(self, page_ref: list, page_lock: threading.RLock) -> None:
        """Start the worker threads. `page_ref` is a 1-element list
        containing the active Playwright page. `page_lock` is the lock
        shared with the main bot for browser coordination."""
        self._page_lock = page_lock
        self._stop_event.clear()
        self._approval_thread = threading.Thread(
            target=self._approval_loop,
            args=(page_ref,),
            name="approval-worker",
            daemon=True,
        )
        self._retry_thread = threading.Thread(
            target=self._retry_loop,
            args=(page_ref,),
            name="retry-worker",
            daemon=True,
        )
        self._approval_thread.start()
        self._retry_thread.start()
        logger.info("[Worker] Approval & retry workers started")

    def stop(self) -> None:
        """Signal workers to stop."""
        self._stop_event.set()

    def _approval_loop(self, page_ref: list) -> None:
        """Process approved items from the approval queue."""
        while not self._stop_event.is_set():
            try:
                time.sleep(settings.auto_sender_interval)
                self._process_one_approval(page_ref)
            except Exception as e:
                logger.error(f"[Worker] Approval loop error: {e}\n{traceback.format_exc()}")
                time.sleep(5)

    def _process_one_approval(self, page_ref: list) -> None:
        """Find and process one approved item."""
        approved = approval_queue.list_all(status="approved")
        if not approved:
            return

        for item_data in approved:
            if self._stop_event.is_set():
                return
            msg_id = item_data.get("msg_id")
            if not msg_id:
                continue

            # Atomically claim the item
            item = approval_queue.claim_for_processing(msg_id)
            if item is None:
                continue  # Already claimed by another iteration

            self._send_approval_item(page_ref, item)

    def _send_approval_item(self, page_ref: list, item: ApprovalItem) -> None:
        """Send a single approved item."""
        page = page_ref[0] if page_ref else None
        if page is None:
            approval_queue.mark_failed(item.msg_id, "No browser page available")
            return

        try:
            with self._page_lock:
                # Open chat
                if not navigation.open_chat(page, item.contact):
                    approval_queue.mark_failed(item.msg_id, "Could not open chat")
                    return

                # Simulate reading
                human.simulate_reading(item.messages)

                # Build processed messages for the AI
                from media.whatsapp.core.types import ProcessedMessage, MessageKind
                processed = []
                for m in item.messages:
                    try:
                        kind = MessageKind(m.get("history_type", "text"))
                    except ValueError:
                        kind = MessageKind.TEXT
                    processed.append(ProcessedMessage(
                        label=m.get("label", "Text"),
                        content=m.get("content", ""),
                        kind=kind,
                        caption=m.get("caption", ""),
                    ))

                # Generate or use custom reply
                if item.custom_reply:
                    reply = item.custom_reply
                else:
                    from media.whatsapp.ai.router import router
                    history = history_manager.load(item.contact)
                    history_str = history_manager.format_for_prompt(
                        history, settings.gemini_max_chars - 4000,
                    )
                    persona = persona_manager.get(item.contact)
                    reply = router.reply(
                        persona, history_str, processed, item.custom_context,
                    )

                # Simulate typing
                typing_duration = human.simulate_typing_delay(reply)
                time.sleep(min(typing_duration, 8.0))

                # Send
                human.reply_delay()  # Wait before sending
                sent = sender.send(page, reply)

                if sent:
                    # Update history
                    history = history_manager.load(item.contact)
                    for pm in processed:
                        history = history_manager.append(
                            item.contact, history, "user",
                            pm.content, pm.kind.value if hasattr(pm.kind, "value") else "text",
                        )
                    history_manager.append(
                        item.contact, history, "assistant", reply, "text",
                    )
                    approval_queue.mark_sent(item.msg_id)
                    metrics.inc("approval_processed", status="sent")
                    logger.info(f"[Worker] Sent approved reply to {item.contact}")
                else:
                    approval_queue.mark_failed(item.msg_id, "Send failed")
                    # Add to retry queue with current attempt count
                    retry_queue.add(
                        item.contact, reply,
                        attempt=item.attempts,
                        last_error="Send failed in approval worker",
                    )

                navigation.close_chat(page)
                human.post_send_pause()

        except Exception as e:
            logger.error(
                f"[Worker] Approval item {item.msg_id} error: {e}\n"
                f"{traceback.format_exc()}"
            )
            approval_queue.mark_failed(item.msg_id, str(e))

    def _retry_loop(self, page_ref: list) -> None:
        """Process due items from the retry queue."""
        while not self._stop_event.is_set():
            try:
                time.sleep(settings.retry_worker_interval)
                self._process_retries(page_ref)
            except Exception as e:
                logger.error(f"[Worker] Retry loop error: {e}\n{traceback.format_exc()}")
                time.sleep(5)

    def _process_retries(self, page_ref: list) -> None:
        """Send all due retry items."""
        items = retry_queue.due_items()
        if not items:
            return

        page = page_ref[0] if page_ref else None
        if page is None:
            return

        for item in items:
            if self._stop_event.is_set():
                return
            try:
                with self._page_lock:
                    if not navigation.open_chat(page, item.contact):
                        retry_queue.reschedule(
                            item.file_path, item.attempt, "Could not open chat"
                        )
                        continue
                    sent = sender.send(page, item.reply)
                    navigation.close_chat(page)

                if sent:
                    retry_queue.remove(item.file_path)
                    metrics.inc("retry_success", attempt=item.attempt)
                    logger.info(f"[Worker] Retry success for {item.contact}")
                else:
                    retry_queue.reschedule(
                        item.file_path, item.attempt, "Send failed"
                    )
            except Exception as e:
                logger.error(f"[Worker] Retry item error: {e}")
                retry_queue.reschedule(item.file_path, item.attempt, str(e))


# Singleton
queue_worker = QueueWorker()
