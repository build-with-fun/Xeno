"""Main Bot orchestrator: ties together all subsystems.

This is the central coordinator that:
1. Manages the browser lifecycle (BrowserManager)
2. Injects WPP.js (WPPManager)
3. Scans the sidebar for unread messages (SidebarScanner)
4. Processes each contact (fetch messages → classify → process media →
   decide safety → reply OR enqueue for approval)
5. Runs background workers (approval & retry queues)
6. Runs the admin API server
7. Handles graceful shutdown

Fixes the original code's issues:
- `pending_contacts.pop()` happened BEFORE process_contact ran — if
  processing crashed, the message was permanently lost. Now we only
  pop AFTER successful processing (or on permanent failure).
- No page lock coordination between main loop and workers.
- No reload backoff — reload happened immediately after failure.
- No graceful shutdown of worker threads.
"""
from __future__ import annotations

import random
import threading
import time
import traceback
from datetime import datetime
from typing import Optional

from media.whatsapp.ai.router import router, SAFE_FALLBACK
from media.whatsapp.analytics.tracker import analytics
from media.whatsapp.browser.manager import browser
from media.whatsapp.browser.navigation import navigation
from media.whatsapp.browser.scanner import scanner
from media.whatsapp.browser.sender import sender
from media.whatsapp.browser.wpp import wpp
from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import NonReplyableError
from media.whatsapp.filter import contact_filter
from media.whatsapp.core.types import Decision, Message, MessageKind, ProcessedMessage
from media.whatsapp.human.behavior import human
from media.whatsapp.media.docx import docx_processor
from media.whatsapp.media.image import image_processor
from media.whatsapp.media.image_gen import image_generator
from media.whatsapp.media.pdf import pdf_processor
from media.whatsapp.media.voice import voice_processor
from media.whatsapp.memory.history import history_manager
from media.whatsapp.memory.personas import persona_manager
from media.whatsapp.memory.seen import seen_tracker
from media.whatsapp.observability.health import health
from media.whatsapp.observability.logging_setup import get_logger, setup_logging
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.taskqueue.approval import approval_queue
from media.whatsapp.taskqueue.retry import retry_queue
from media.whatsapp.taskqueue.worker import queue_worker
from media.whatsapp.safety.keywords import keyword_alerts
from media.whatsapp.safety.rate_limiter import rate_limiter
from media.whatsapp.utils.crypto import hmac_sign

logger = get_logger(__name__)


class Bot:
    """The main WhatsApp bot orchestrator."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._page_lock = threading.RLock()
        # `pending` tracks contacts with unread messages waiting to be processed.
        # Contact -> {last_seen, preview, mtype}
        self.pending: dict[str, dict] = {}
        self._pending_lock = threading.RLock()
        self._last_reload_time: float = 0.0
        self._reload_cooldown: float = 30.0  # Don't reload more than once per 30s
        # Track retries per contact to avoid infinite retry loops
        self._retry_counts: dict[str, int] = {}
        self._max_retries: int = 5  # Remove from pending after 5 failures
        # Inject the summarizer into history manager
        history_manager.set_summarizer(router.summarize)
        # Set up webhook for keyword alerts
        keyword_alerts.set_webhook(self._fire_webhook)
        # Register health checks
        self._register_health_checks()

    # ── Public API ───────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the bot: launch browser, inject WPP, scan loop."""
        self._print_banner()
        self._validate_config()

        # Load persistent state
        seen_tracker.load()
        self._load_pending_state()

        # Start admin API in background
        try:
            from media.whatsapp.api.server import admin_server, set_bot
            set_bot(self)
            admin_server.start()
        except Exception as e:
            logger.warning(f"[Bot] Could not start admin API: {e}")

        # Start browser
        browser.start()
        if not browser.wait_for_whatsapp():
            logger.error("[Bot] WhatsApp Web did not load in time")
            return

        if not wpp.inject(browser.page):
            logger.error("[Bot] WPP.js injection failed — some features will be limited")

        page_ref = [browser.page]
        queue_worker.start(page_ref, self._page_lock)

        logger.info("[Bot] Active and scanning for messages!")
        metrics.set("bot_running", 1.0)

        # Main scan loop
        try:
            self._main_loop(page_ref)
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the bot to stop gracefully."""
        logger.info("[Bot] Stop requested")
        self._stop_event.set()
        queue_worker.stop()

    # ── Main loop ────────────────────────────────────────────────────────────
    def _main_loop(self, page_ref: list) -> None:
        """The main scan-and-process loop."""
        last_scan = 0.0
        scan_interval = human.scan_interval()

        while not self._stop_event.is_set():
            # Check stop signal file
            if settings.stop_signal_path.exists():
                logger.info("[Bot] Stop signal file detected")
                break

            page = page_ref[0] if page_ref else None
            if page is None:
                logger.error("[Bot] No browser page — exiting main loop")
                break

            # WhatsApp alive check
            if not browser.is_alive():
                if not self._reload_whatsapp(page_ref):
                    # Reload failed — wait before retrying
                    time.sleep(10)
                continue

            # Scan sidebar
            now = time.time()
            if now - last_scan >= scan_interval:
                try:
                    scanner.scan(page, self.pending)
                except Exception as e:
                    logger.warning(f"[Bot] Scan error: {e}")
                last_scan = now
                scan_interval = human.scan_interval()
                metrics.set("pending_contacts", len(self.pending))
                self._save_pending_state()

            # Process due contacts
            ready = self._get_ready_contacts()
            for contact, info in ready:
                if self._stop_event.is_set():
                    break
                self._process_contact_safe(page_ref, contact, info)

            # Idle handling
            if not ready:
                time.sleep(0.2)

    def _get_ready_contacts(self) -> list[tuple[str, dict]]:
        """Return contacts whose batch window has elapsed."""
        now = time.time()
        with self._pending_lock:
            ready = [
                (c, info) for c, info in self.pending.items()
                if (now - info.get("last_seen", 0)) >= settings.batch_window_secs
            ]
        return ready

    def _process_contact_safe(
        self, page_ref: list, contact: str, info: dict,
    ) -> None:
        """Wrap process_contact with error handling & state cleanup.

        Critical fix: only remove the contact from `pending` AFTER successful
        processing. On error, keep it in pending (with a fresh timestamp) so
        it gets retried on the next scan.

        Retry limit: after `_max_retries` consecutive failures, the contact
        is removed from pending to prevent infinite retry loops (e.g. WhatsApp
        Business broadcast chat that has no input box).
        """
        page = page_ref[0] if page_ref else None
        if page is None:
            return

        # Contact filter check — skip if not allowed (allowlist/blocklist)
        if not contact_filter.is_allowed(contact):
            logger.info(f"[Bot] Skipping {contact} (filtered by allowlist/blocklist)")
            with self._pending_lock:
                self.pending.pop(contact, None)
            self._retry_counts.pop(contact, None)
            return

        try:
            with self._page_lock:
                success = self._process_contact(page, contact, info)
            if success:
                with self._pending_lock:
                    self.pending.pop(contact, None)
                self._retry_counts.pop(contact, None)
            else:
                retries = self._retry_counts.get(contact, 0) + 1
                self._retry_counts[contact] = retries
                if retries >= self._max_retries:
                    logger.warning(
                        f"[Bot] {contact} failed {retries} times — removing from pending"
                    )
                    with self._pending_lock:
                        self.pending.pop(contact, None)
                    self._retry_counts.pop(contact, None)
                else:
                    logger.warning(
                        f"[Bot] {contact} failed attempt {retries}/{self._max_retries}"
                    )
                    with self._pending_lock:
                        if contact in self.pending:
                            self.pending[contact]["last_seen"] = time.time() + 30 * retries
        except NonReplyableError:
            logger.warning(
                f"[Bot] {contact} is non-replyable (announcement group/broadcast) — "
                f"removing from pending permanently"
            )
            jid = info.get("jid", "")
            if jid:
                try:
                    navigation.mark_chat_read(page, jid)
                except Exception:
                    pass
            with self._pending_lock:
                self.pending.pop(contact, None)
            self._retry_counts.pop(contact, None)
            try:
                navigation.close_chat(page)
            except Exception:
                pass
        except Exception as e:
            logger.error(
                f"[Bot] process_contact({contact}) error: {e}\n"
                f"{traceback.format_exc()}"
            )
            retries = self._retry_counts.get(contact, 0) + 1
            self._retry_counts[contact] = retries
            if retries >= self._max_retries:
                logger.warning(
                    f"[Bot] {contact} failed {retries} times (exception) — removing from pending"
                )
                with self._pending_lock:
                    self.pending.pop(contact, None)
                self._retry_counts.pop(contact, None)
            else:
                with self._pending_lock:
                    if contact in self.pending:
                        self.pending[contact]["last_seen"] = time.time() + 30 * retries
            try:
                navigation.close_chat(page)
            except Exception:
                pass

    def _process_contact(self, page, contact: str, info: dict) -> bool:
        """Process unread messages for a contact. Returns True on success."""
        logger.info(f"[Bot] Processing: {contact}")
        analytics.track(contact, "received")
        start_time = time.time()

        jid = info.get("jid", "")
        if not navigation.open_chat(page, contact, jid):
            logger.error(f"[Bot] Could not open chat for {contact}")
            return False

        # Fetch unread messages — try WPP.js first, then fall back to DOM
        raw_msgs = self._fetch_unread_messages(page, contact)
        if not raw_msgs:
            raw_msgs = self._read_messages_from_dom(page)
            if raw_msgs:
                logger.info(f"[Bot] Got {len(raw_msgs)} messages via DOM fallback for {contact}")
        if not raw_msgs:
            logger.warning(f"[Bot] No unread messages fetched for {contact}")
            return True  # Treat as success — nothing to do

        # ── Command detection ─────────────────────────────────────────────────
        # Process commands but continue with remaining messages.
        for raw in raw_msgs:
            body = (raw.get("body") or "").strip()

            if body.lower() == "/clear":
                msg = Message.from_wpp(raw)
                if msg.id:
                    seen_tracker.mark_seen(msg.id)
                history_manager.clear(contact)
                continue

            if body.lower().startswith("/image "):
                msg = Message.from_wpp(raw)
                if msg.id:
                    seen_tracker.mark_seen(msg.id)
                prompt = body[7:].strip().strip('"').strip("'")
                if prompt:
                    gemini_key = image_generator.get_available_key(settings.gemini_api_keys)
                    if gemini_key:
                        sender.send(page, f"Generating: \"{prompt[:60]}\"...")
                        try:
                            img_bytes, mime = image_generator.generate(prompt, gemini_key)
                            sender.send_image(page, img_bytes, caption=prompt)
                        except Exception as e:
                            logger.error(f"[Bot] Image generation failed: {e}")
                            sender.send(page, f"Image generation failed: {e}")
                    else:
                        logger.warning("[Bot] All Gemini image keys in cooldown — skipping image generation")
                        sender.send(page, "Image generation currently unavailable (all keys rate-limited)")
                continue

        # Process each message
        processed: list[ProcessedMessage] = []
        all_text_parts: list[str] = []

        for raw in raw_msgs:
            msg = Message.from_wpp(raw)
            if not msg.id:
                continue
            if seen_tracker.is_duplicate(msg.id):
                continue
            if msg.from_me:
                seen_tracker.mark_seen(msg.id)
                continue

            pm = self._process_single_message(page, msg)
            if pm is None:
                continue  # skipped (e.g., video)

            seen_tracker.mark_seen(msg.id)
            analytics.track(contact, "received_type", pm.kind.value if hasattr(pm.kind, "value") else str(pm.kind))
            processed.append(pm)
            all_text_parts.append(f"[{pm.label}]: {pm.content}")

        if not processed:
            logger.info(f"[Bot] All messages deduplicated for {contact}")
            if jid:
                navigation.mark_chat_read(page, jid)
            navigation.close_chat(page)
            return True

        # Keyword alerts
        full_text = "\n".join(all_text_parts)
        keyword_alerts.check(contact, full_text)

        # Rate limit check
        if not rate_limiter.can_reply(contact):
            logger.warning(
                f"[Bot] {contact} is rate-limited, skipping reply "
                f"(status: {rate_limiter.status(contact)})"
            )
            if jid:
                navigation.mark_chat_read(page, jid)
            navigation.close_chat(page)
            return True

        # Decision engine
        history = history_manager.load(contact)
        history_str = history_manager.format_for_prompt(
            history, settings.gemini_max_chars - 4000,
        )
        decision = router.decide(full_text, history_str)

        # Approval needed?
        if decision.needs_approval:
            approval_queue.add(contact, processed, decision)
            analytics.track(contact, "approval_needed")
            if jid:
                navigation.mark_chat_read(page, jid)
            navigation.close_chat(page)
            return True

        # Retraction?
        if decision.is_retraction:
            reply = decision.retraction_reply or "Haha no worries! :)"
        else:
            persona = persona_manager.get(contact)
            reply = router.reply(persona, history_str, processed, "")

        # Append user messages to history BEFORE sending
        for pm in processed:
            history = history_manager.append(
                contact, history, "user", pm.content,
                pm.kind.value if hasattr(pm.kind, "value") else "text",
            )

        # Mark chat as read (clear unread in WhatsApp)
        if jid:
            navigation.mark_chat_read(page, jid)

        # Simulate reading & typing
        human.simulate_reading(processed)
        typing_dur = human.simulate_typing_delay(reply)
        time.sleep(min(typing_dur, 8.0))
        human.reply_delay()

        # Send
        sent = sender.send(page, reply)

        if sent:
            history_manager.append(contact, history, "assistant", reply, "text")
            rate_limiter.record_reply(contact)
            analytics.track(contact, "sent")
            elapsed = time.time() - start_time
            analytics.track(contact, "response_time", elapsed)
            logger.info(
                f"[Bot] Reply sent to {contact} ({len(reply)} chars, "
                f"{elapsed:.1f}s): {reply[:60]!r}"
            )
        else:
            retry_queue.add(contact, reply, attempt=0, last_error="Initial send failed")
            analytics.track(contact, "send_failed")
            self._fire_webhook("send_failed", {
                "contact": contact, "reply_preview": reply[:80],
            })

        navigation.close_chat(page)
        human.post_send_pause()
        return True

    def _process_single_message(
        self, page, msg: Message,
    ) -> Optional[ProcessedMessage]:
        """Process a single raw message into a ProcessedMessage."""
        if msg.kind == MessageKind.VIDEO:
            logger.info(f"[Bot] Skipping video message")
            seen_tracker.mark_seen(msg.id)
            return None

        pm = ProcessedMessage(
            label="Text",
            content="",
            kind=msg.kind,
            caption=msg.caption,
            raw_msg_id=msg.id,
        )

        if msg.kind == MessageKind.TEXT:
            pm.content = msg.body
            pm.label = "Text"
        elif msg.kind == MessageKind.VOICE:
            transcript = voice_processor.transcribe(page, msg.id)
            pm.content = f"[Voice Note Transcript]: {transcript}"
            pm.label = "Recording"
        elif msg.kind == MessageKind.IMAGE:
            content, img_bytes, mime = image_processor.analyze(page, msg.id, msg.caption)
            pm.content = content
            pm.image_bytes = img_bytes
            pm.mimetype = mime or "image/jpeg"
            pm.label = "Image"
        elif msg.kind == MessageKind.PDF:
            pm.content = pdf_processor.extract(page, msg.id, msg.caption)
            pm.label = "PDF"
        elif msg.kind == MessageKind.DOCX:
            pm.content = docx_processor.extract(page, msg.id, msg.caption)
            pm.label = "Document"
        elif msg.kind == MessageKind.STICKER:
            pm.content = "[Sticker]"
            pm.label = "Sticker"
        else:
            pm.content = msg.body or "[Message]"
            pm.label = "Text"

        if not pm.content:
            pm.content = f"[{pm.label}]"

        return pm

    def _fetch_unread_messages(self, page, contact: str) -> list[dict]:
        """Fetch unread messages via WPP.js. Returns list of raw message dicts.

        Research notes (July 2026):
        - WPP.chat.list({ onlyWithUnreadMessage: true }) IS NOT a real WPP.js option.
          It was made up by the original code author and silently returns all chats or errors.
        - Use WPP.chat.getUnreadChats() when available, or filter c.unreadCount > 0.
        - WPP.chat.getMessages(chatId, { count: N, onlyUnread: true }) is the correct API.
        - Names are matched against: name, pushname, formattedTitle, and id.user (phone).
        """
        js = """
        async (targetName) => {
            try {
                const lower = targetName.toLowerCase().trim();
                const phone = lower.replace(/[^\\d]/g, '');

                // Get chats from ChatStore (reliable internal collection)
                const store = window.WPP?.whatsapp?.ChatStore;
                if (!store) return [];
                const models = store.getModelsArray();
                if (!models || !models.length) return [];

                const norm = s => s.toLowerCase().replace(/[^\\w\\d]/g, '');

                let chat = null;
                for (const c of models) {
                    const n = (c.name || c.pushname || c.formattedTitle || '').toLowerCase().trim();
                    const userId = (c.id?.user || '').toLowerCase();
                    const userPhone = userId.replace(/[^\\d]/g, '');
                    if (n === lower || userId === lower || userPhone === phone) {
                        chat = c; break;
                    }
                }
                if (!chat) {
                    for (const c of models) {
                        const n = (c.name || c.pushname || c.formattedTitle || '').toLowerCase().trim();
                        const userId = (c.id?.user || '').toLowerCase();
                        if (norm(n) === norm(lower) || norm(userId) === norm(lower) || norm(userId) === norm(phone)) {
                            chat = c; break;
                        }
                    }
                }
                if (!chat) {
                    for (const c of models) {
                        const n = (c.name || c.pushname || c.formattedTitle || '').toLowerCase().trim();
                        const userId = (c.id?.user || '').toLowerCase();
                        if (n.includes(lower) || lower.includes(n) || userId.includes(lower) || lower.includes(userId)) {
                            chat = c; break;
                        }
                    }
                }
                if (!chat) return [];

                const count = Math.min(chat.unreadCount || 10, 30);
                const msgs = await WPP.chat.getMessages(chat.id._serialized, {
                    count: count + 5,
                    onlyUnread: true,
                });
                return (msgs || [])
                    .filter(m => !m.fromMe)
                    .map(m => ({
                        id: m.id?._serialized || m.id?.id || '',
                        type: m.type || 'text',
                        body: m.body || '',
                        caption: m.caption || '',
                        filename: m.filename || '',
                        mimetype: m.mimetype || '',
                        fromMe: m.fromMe || false,
                        t: m.t || 0,
                    }));
            } catch(e) {
                return [];
            }
        }
        """
        try:
            return page.evaluate(js, contact) or []
        except Exception as e:
            logger.error(f"[Bot] FetchUnread {contact}: {e}")
            return []

    def _read_messages_from_dom(self, page) -> list[dict]:
        """Read visible incoming messages from the open chat's DOM.

        Fallback when WPP.js message fetching fails. Handles WhatsApp Web's
        virtualized DOM by scrolling to load messages into view.

        Research notes (July 2026):
        - WhatsApp Web uses DOM virtualization: only ~20-30 messages rendered at a time.
          Messages outside the viewport are NOT in the DOM. Must scroll to load.
        - span.selectable-text class is GONE in newer WhatsApp Web (removed ~2025 Q4).
          Messages now use span[dir="ltr|rtl"] for text.
        - The most reliable message selector is [data-pre-plain-text] attribute,
          present on every message bubble with format: "[HH:MM AM/PM, M/D/YYYY] Sender:"
        - .message-in / .message-out classes are still present and reliable.
        """
        js = """
        async () => {
            const msgs = [];
            const seenKeys = new Set();

            // Helper to extract message text from a container element
            function extractBody(el) {
                // Tier 1: selectable-text (legacy, pre-2025)
                const st = el.querySelector('span.selectable-text');
                if (st) return st.innerText.trim();
                // Tier 2: span[dir="ltr"|"rtl"] (2025+ WhatsApp Web)
                const dirSpan = el.querySelector('span[dir="ltr"], span[dir="rtl"]');
                if (dirSpan) return dirSpan.innerText.trim();
                // Tier 3: walk all descendant text nodes, skip icons and timestamps
                let text = '';
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (!t) continue;
                    // Skip emoji-only, icon ligatures, timestamp patterns
                    if (/^[\\u2600-\\u27BF\\uD800-\\uDBFF\\uDC00-\\uDFFF\\s]+$/.test(t)) continue;
                    if (/^\\d{1,2}:\\d{2}(\\s?[AP]M)?$/i.test(t)) continue;
                    if (/^[✓✓🔇]$/.test(t)) continue;
                    text += t + ' ';
                }
                return text.trim() || (el.innerText || '').trim();
            }

                    // Always return 'text' — DOM IDs aren't real WPP IDs,
            // so WPP.chat.getMessageById() / downloadMedia() will fail.
            // Media processing is only possible via WPP.getMessages().
            function classifyType(el) { return 'text'; }

            // Find the message scroll container (the virtualized list)
            function getScrollContainer() {
                const candidates = document.querySelectorAll(
                    'div[tabindex="0"][role="application"], ' +
                    'div[data-testid="conversation-panel-messages"], ' +
                    '#main > div > div:first-child > div:first-child > div:last-child, ' +
                    'div[tabindex="0"]'
                );
                for (const c of candidates) {
                    if (c.scrollHeight > c.clientHeight && c.scrollHeight > 500) return c;
                }
                return document.querySelector('[data-testid="conversation-panel-messages"]')
                    || document.querySelector('div[tabindex="0"]:last-child');
            }

            const container = getScrollContainer();
            if (!container) return [];

            // Step 1: scroll to top to load earliest visible messages
            container.scrollTop = 0;
            await new Promise(r => setTimeout(r, 600));

            // Step 2: scroll down incrementally, extracting messages at each stop
            // This handles the virtualized DOM — only ~20-30 messages are rendered at once
            const scrollStep = Math.max(container.clientHeight * 0.7, 200);
            let emptyScrolls = 0;
            const MAX_EMPTY_SCROLLS = 8;

            for (let i = 0; i < 60; i++) {
                // Extract messages currently in DOM
                const msgEls = container.querySelectorAll(
                    '[data-pre-plain-text], ' +
                    'div.message-in, ' +
                    'div[data-testid="msg-container"].message-in, ' +
                    'div[data-testid="conversation-panel-messages"] [data-testid="msg-container"]'
                );

                let addedCount = 0;
                msgEls.forEach(el => {
                    // Skip outgoing messages
                    if (el.matches('.message-out') || el.querySelector('[data-testid="msg-dblcheck"], [data-testid="msg-check"]')) return;

                    const body = extractBody(el);
                    if (!body) return;

                    // Use data-pre-plain-text as dedup key (it's stable per message)
                    const prePlain = el.getAttribute('data-pre-plain-text') || '';
                    const key = prePlain ? prePlain + '|' + body.substring(0, 60) : body.substring(0, 60);
                    if (seenKeys.has(key)) return;
                    seenKeys.add(key);

                    // Try to extract the real WhatsApp message ID from the DOM
                    // WhatsApp Web stores the msg ID in data-id or data-testid attributes
                    let realId = '';
                    const idEl = el.closest('[data-id]');
                    if (idEl) realId = idEl.getAttribute('data-id') || '';
                    if (!realId) {
                        // Try data-testid="msg-container" -> the container's inner data-id
                        const ctr = el.closest('[data-testid="msg-container"]');
                        if (ctr) realId = ctr.getAttribute('data-id') || ctr.getAttribute('id') || '';
                    }
                    // Stable content-based hash for dedup (never use Date.now())
                    if (!realId) {
                        const contentKey = (prePlain + '|' + body.substring(0, 80)).replace(/\\s+/g, ' ');
                        let hash = 0;
                        for (let i = 0; i < contentKey.length; i++) {
                            const chr = contentKey.charCodeAt(i);
                            hash = ((hash << 5) - hash) + chr;
                            hash |= 0;
                        }
                        realId = 'c_' + Math.abs(hash).toString(36);
                    }

                    const type = classifyType(el);
                    msgs.push({
                        id: realId,
                        type: type,
                        body: body,
                        caption: '',
                        fromMe: false,
                        t: Math.floor(Date.now() / 1000) - (msgs.length * 2),
                    });
                    addedCount++;
                });

                if (addedCount === 0) {
                    emptyScrolls++;
                    if (emptyScrolls >= MAX_EMPTY_SCROLLS) break;
                } else {
                    emptyScrolls = 0;
                }

                // Scroll down to load more messages
                container.scrollTop += scrollStep;
                await new Promise(r => setTimeout(r, 350));
            }

            // Step 3: scroll back to bottom (for UI consistency)
            container.scrollTop = container.scrollHeight;
            await new Promise(r => setTimeout(r, 300));

            // Return messages in chronological order (oldest first)
            return msgs.reverse();
        }
        """
        try:
            result = page.evaluate(js) or []
            if result:
                logger.info(f"[Bot] DOM reader extracted {len(result)} messages")
            return result
        except Exception as e:
            logger.warning(f"[Bot] DOM reader error: {e}")
            return []

    # ── Reload & recovery ────────────────────────────────────────────────────
    def _reload_whatsapp(self, page_ref: list) -> bool:
        """Reload WhatsApp Web with cooldown."""
        now = time.time()
        if now - self._last_reload_time < self._reload_cooldown:
            wait = self._reload_cooldown - (now - self._last_reload_time)
            logger.info(f"[Bot] Reload cooldown — waiting {wait:.0f}s")
            time.sleep(wait)
            return False

        self._last_reload_time = now
        logger.warning("[Bot] WhatsApp Web not responding, reloading...")
        metrics.inc("whatsapp_reloads")
        if browser.reload():
            # Re-inject WPP.js
            if wpp.inject(browser.page):
                page_ref[0] = browser.page
                # Wait a bit for things to settle
                time.sleep(random.uniform(8, 14))
                return True
        return False

    # ── State persistence ────────────────────────────────────────────────────
    def _load_pending_state(self) -> None:
        """Load pending contacts from disk."""
        from media.whatsapp.memory.store import store
        data = store.read_raw(settings.pending_state_path, {}) or {}
        cutoff = time.time() - 300  # 5 minutes
        with self._pending_lock:
            for k, v in data.items():
                if v.get("last_seen", 0) > cutoff:
                    self.pending[k] = v
        if self.pending:
            logger.info(f"[Bot] Restored {len(self.pending)} pending contacts from disk")

    def _save_pending_state(self) -> None:
        """Persist pending contacts to disk."""
        from media.whatsapp.memory.store import store
        with self._pending_lock:
            data = {
                k: {
                    "last_seen": v.get("last_seen", 0),
                    "preview": v.get("preview", ""),
                    "mtype": v.get("mtype", "text"),
                }
                for k, v in self.pending.items()
            }
        try:
            store.write_raw(settings.pending_state_path, data)
        except Exception as e:
            logger.warning(f"[Bot] Pending state save failed: {e}")

    # ── Webhook ──────────────────────────────────────────────────────────────
    def _fire_webhook(self, event_type: str, data: dict) -> None:
        """Fire a webhook event (if WEBHOOK_URL is configured)."""
        if not settings.webhook_url:
            return

        def _send():
            try:
                import json
                import requests
                payload = json.dumps({
                    "event": event_type,
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                }, default=str)
                headers = {"Content-Type": "application/json"}
                if settings.webhook_secret:
                    headers["X-Signature"] = hmac_sign(settings.webhook_secret, payload)
                r = requests.post(
                    settings.webhook_url, data=payload,
                    headers=headers, timeout=5,
                )
                if not r.ok:
                    # One retry
                    requests.post(
                        settings.webhook_url, data=payload,
                        headers=headers, timeout=5,
                    )
            except Exception as e:
                logger.warning(f"[Webhook] {e}")

        threading.Thread(target=_send, daemon=True).start()

    # ── Health checks ────────────────────────────────────────────────────────
    def _register_health_checks(self) -> None:
        """Register probes for the /api/health endpoint."""
        health.register("browser", self._health_browser)
        health.register("whatsapp_alive", self._health_whatsapp)
        health.register("wpp_ready", self._health_wpp)
        health.register("ai_providers", self._health_ai)
        health.register("queue_worker", self._health_worker)
        health.register("seen_tracker", self._health_seen)

    def _health_browser(self) -> tuple[bool, str]:
        if browser.page is None:
            return False, "Browser not started"
        return True, "Browser running"

    def _health_whatsapp(self) -> tuple[bool, str]:
        if not browser.page:
            return False, "No page"
        return (True, "WhatsApp alive") if browser.is_alive() else (False, "WhatsApp not responding")

    def _health_wpp(self) -> tuple[bool, str]:
        if not browser.page:
            return False, "No page"
        return (True, "WPP ready") if wpp.is_injected(browser.page) else (False, "WPP not ready")

    def _health_ai(self) -> tuple[bool, str]:
        avail = [p for p in router.providers if not p.is_on_cooldown() and p.is_available()]
        total = len(router.providers)
        if not avail:
            return False, f"0/{total} providers available (all on cooldown or unconfigured)"
        return True, f"{len(avail)}/{total} providers available"

    def _health_worker(self) -> tuple[bool, str]:
        if queue_worker._approval_thread and queue_worker._approval_thread.is_alive():
            return True, "Workers running"
        return False, "Workers not running"

    def _health_seen(self) -> tuple[bool, str]:
        stats = seen_tracker.stats()
        return True, f"{stats['in_memory_count']} IDs in memory"

    # ── Shutdown ─────────────────────────────────────────────────────────────
    def _shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("[Bot] Shutting down...")
        metrics.set("bot_running", 0.0)
        queue_worker.stop()
        self._save_pending_state()
        seen_tracker.flush()
        # Count pending approvals
        pending_count = approval_queue.count("pending")
        if pending_count:
            logger.info(f"[Bot] {pending_count} pending approvals in queue")
        browser.stop()
        # Remove stop signal file
        try:
            if settings.stop_signal_path.exists():
                settings.stop_signal_path.unlink()
        except OSError:
            pass
        logger.info("[Bot] Shutdown complete")

    # ── Setup helpers ────────────────────────────────────────────────────────
    def _print_banner(self) -> None:
        try:
            from rich.console import Console
            console = Console()
            console.print("""
[bold blue]╔══════════════════════════════════════════════════════════════════╗[/]
[bold blue]║      WhatsApp AI Auto-Responder — Production v2.0.0              ║[/]
[bold blue]║      Multi-provider AI + WPP.js + Playwright Chromium            ║[/]
[bold blue]╚══════════════════════════════════════════════════════════════════╝[/]
""")
            console.print(f"  Gemini keys:  {len(settings.gemini_api_keys)}")
            console.print(f"  Groq keys:    {len(settings.groq_api_keys)}")
            console.print(f"  OpenAI keys:  {len(settings.openai_api_keys)}")
            console.print(f"  STT server:   {settings.stt_server_url}")
            console.print(f"  Batch window: {settings.batch_window_secs}s")
            console.print(f"  Scan interval:{settings.scan_interval_min}-{settings.scan_interval_max}s")
            console.print(f"  Summary at:   {settings.summary_threshold} messages")
            console.print(f"  Rate limit:   {settings.rate_limit_per_hour}/hour per contact")
            console.print(f"  Admin API:    http://{settings.admin_host}:{settings.admin_port}")
            console.print()
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Fallback for Windows consoles that don't support Unicode
            print("=" * 66)
            print("      WhatsApp AI Auto-Responder -- Production v2.0.0")
            print("      Multi-provider AI + WPP.js + Playwright Chromium")
            print("=" * 66)
            print(f"  Gemini keys:  {len(settings.gemini_api_keys)}")
            print(f"  Groq keys:    {len(settings.groq_api_keys)}")
            print(f"  OpenAI keys:  {len(settings.openai_api_keys)}")
            print(f"  STT server:   {settings.stt_server_url}")
            print(f"  Batch window: {settings.batch_window_secs}s")
            print(f"  Scan interval:{settings.scan_interval_min}-{settings.scan_interval_max}s")
            print(f"  Summary at:   {settings.summary_threshold} messages")
            print(f"  Rate limit:   {settings.rate_limit_per_hour}/hour per contact")
            print(f"  Admin API:    http://{settings.admin_host}:{settings.admin_port}")
            print()

    def _validate_config(self) -> None:
        """Validate configuration and exit on critical errors."""
        problems = settings.validate()
        for p in problems:
            logger.warning(f"[Config] {p}")
        only_problem_is_no_keys = (
            len(problems) == 1 and "API keys" in problems[0]
        )
        if only_problem_is_no_keys and settings._is_ollama_mode():
            logger.info("[Config] No API keys but Ollama detected OK — skipping key check")
        elif not (settings.gemini_api_keys or settings.groq_api_keys
                or settings.openai_api_keys or settings.anthropic_api_keys):
            logger.error(
                "No AI API keys found! Set at least one of: "
                "GEMINI_API_KEY_1, GROQ_API_KEY_1, OPENAI_API_KEY_1"
            )
            import sys
            sys.exit(1)
