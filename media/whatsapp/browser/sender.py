"""Message sender with multi-method fallback and verification.

Fixes the original code's issues:
- No verification that a message was actually sent (just pressed Enter)
- Clipboard method required permission grant and could silently fail
- `keyboard.type` with very long messages could trigger WhatsApp's
  anti-paste protection
- No detection of WhatsApp's "waiting for network" or other transient errors
"""
from __future__ import annotations

import json
import random
import time
from typing import Optional

from media.whatsapp.browser.navigation import navigation, INPUT_SELECTORS
from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import SendError
from media.whatsapp.human.behavior import human
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)


class MessageSender:
    """Send messages via WhatsApp Web with verification."""

    def send(self, page, text: str, verify: bool = True) -> bool:
        """Send a text message. Returns True on success."""
        if not text or not text.strip():
            logger.warning("[Send] Empty message, skipping")
            return False

        # Try WPP.chat.sendText first (most reliable, doesn't need UI focus)
        if self._send_via_wpp(page, text):
            metrics.inc("send_success", method="wpp")
            return True

        # Fallback 1: clipboard paste
        if self._send_via_clipboard(page, text):
            metrics.inc("send_success", method="clipboard")
            return True

        # Fallback 2: keyboard.type
        if self._send_via_keyboard(page, text):
            metrics.inc("send_success", method="keyboard")
            return True

        logger.error(f"[Send] All methods failed for {len(text)}-char message")
        metrics.inc("send_failures")
        return False

    def _send_via_wpp(self, page, text: str) -> bool:
        """Use WPP.chat.sendText to send a message to the currently-open chat."""
        try:
            # WPP's sendTextToChat needs a chat ID; we use the open chat
            result = page.evaluate("""
            async (msg) => {
                try {
                    // Get the currently active chat
                    const chat = await WPP.chat.getActiveChat();
                    if (!chat) return { success: false, error: 'no_active_chat' };
                    const sentMsg = await WPP.chat.sendTextMessage(
                        chat.id._serialized, msg
                    );
                    return { success: true, id: sentMsg.id._serialized };
                } catch(e) {
                    return { success: false, error: String(e) };
                }
            }
            """, text)
            if result and result.get("success"):
                # Give WhatsApp a moment to register the send
                time.sleep(0.3)
                # Best-effort verify: check last outgoing message
                if self._verify_last_message_sent(page, text):
                    return True
                # If verify failed, the send might still have succeeded
                logger.warning("[Send] WPP send succeeded but verification failed (non-fatal)")
                return True
            err = result.get("error") if result else "no_result"
            logger.debug(f"[Send] WPP method failed: {err}")
            return False
        except Exception as e:
            logger.debug(f"[Send] WPP method error: {e}")
            return False

    def _send_via_clipboard(self, page, text: str) -> bool:
        """Focus input box, paste via clipboard, press Enter."""
        try:
            input_el = navigation.find_input_box(page)
            if not input_el:
                logger.warning("[Send] No input box found (clipboard method)")
                return False
            # Set clipboard via JS (works in non-headless Chromium)
            page.evaluate(
                f"navigator.clipboard.writeText({json.dumps(text)})"
            )
            input_el.click()
            time.sleep(0.15)
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
            page.keyboard.press("Control+v")
            time.sleep(0.25)
            # Verify text actually got into the box before pressing Enter
            current = self._read_input_text(page)
            if current.strip() != text.strip():
                logger.warning(
                    f"[Send] Clipboard paste mismatch "
                    f"(got {len(current)} chars, expected {len(text)})"
                )
                # Fall through to keyboard method
                return False
            page.keyboard.press("Enter")
            time.sleep(0.3)
            return self._verify_last_message_sent(page, text)
        except Exception as e:
            logger.warning(f"[Send] Clipboard method error: {e}")
            return False

    def _send_via_keyboard(self, page, text: str) -> bool:
        """Focus input box, type character-by-character, press Enter."""
        try:
            input_el = navigation.find_input_box(page)
            if not input_el:
                logger.warning("[Send] No input box found (keyboard method)")
                return False
            input_el.click()
            time.sleep(0.15)
            # Type with realistic per-keystroke delay
            page.keyboard.type(text, delay=random.randint(15, 35))
            time.sleep(0.2)
            # Verify text is in the box
            current = self._read_input_text(page)
            if current.strip() != text.strip():
                logger.warning(
                    f"[Send] Keyboard type mismatch "
                    f"(got {len(current)} chars, expected {len(text)})"
                )
                # Clear and try clipboard one more time
                page.keyboard.press("Control+a")
                page.keyboard.press("Backspace")
                return False
            page.keyboard.press("Enter")
            time.sleep(0.3)
            return self._verify_last_message_sent(page, text)
        except Exception as e:
            logger.warning(f"[Send] Keyboard method error: {e}")
            return False

    def send_image(self, page, image_bytes: bytes, caption: str = "") -> bool:
        """Send an image to the currently open chat using WPP.js.

        Converts the raw image bytes to a base64 data URI and sends via
        WPP.chat.sendFileMessage().

        Args:
            page: Playwright page object.
            image_bytes: Raw image bytes (PNG or JPEG).
            caption: Optional text caption for the image.

        Returns:
            True if the message was sent successfully.
        """
        try:
            import base64
            b64 = base64.b64encode(image_bytes).decode()
            mime = "image/png"
            data_uri = f"data:{mime};base64,{b64}"

            result = page.evaluate("""
            async (b64DataUri, cap) => {
                try {
                    const chat = await WPP.chat.getActiveChat();
                    if (!chat) return { success: false, error: 'no_active_chat' };
                    const sent = await WPP.chat.sendFileMessage(
                        chat.id._serialized,
                        b64DataUri,
                        {
                            type: 'image',
                            caption: cap || '',
                            filename: 'generated.png',
                        }
                    );
                    return { success: true, id: sent.id };
                } catch(e) {
                    return { success: false, error: String(e) };
                }
            }
            """, data_uri, caption)

            if result and result.get("success"):
                time.sleep(0.3)
                if self._verify_last_image_sent(page):
                    metrics.inc("send_success", method="image_wpp")
                    logger.info(f"[Send] Image sent ({len(image_bytes):,} bytes, caption={caption!r})")
                    return True
                logger.warning("[Send] Image send succeeded but verification failed (non-fatal)")
                return True

            err = result.get("error") if result else "no_result"
            logger.warning(f"[Send] Image send failed: {err}")
            return False
        except Exception as e:
            logger.warning(f"[Send] Image send error: {e}")
            return False

    def _read_input_text(self, page) -> str:
        """Read current text from the input box."""
        try:
            return page.evaluate("""
            () => {
                const el = document.querySelector(
                    'div[contenteditable="true"][data-tab="10"], ' +
                    'div[contenteditable="true"][role="textbox"], ' +
                    'footer div[contenteditable="true"], ' +
                    'div[aria-label="Type a message"], ' +
                    'div[contenteditable="true"]'
                );
                return el ? (el.innerText || el.textContent || '') : '';
            }
            """) or ""
        except Exception:
            return ""

    def _verify_last_message_sent(self, page, expected: str) -> bool:
        """Verify the last outgoing message matches `expected`.

        Checks for the message in the conversation panel and for absence
        of a "sending" / "clock" icon.
        """
        try:
            result = page.evaluate("""
            (expected) => {
                // Find all "from me" message bubbles — try multiple selectors
                let outgoing = document.querySelectorAll(
                    'div[data-testid="msg-container"].message-out'
                );
                if (!outgoing.length) {
                    outgoing = document.querySelectorAll(
                        'div.message-out'
                    );
                }
                if (!outgoing.length) {
                    // Last resort: messages aligned to right
                    const allMsgs = document.querySelectorAll('[data-testid="msg-container"]');
                    outgoing = Array.from(allMsgs).filter(el => {
                        const style = window.getComputedStyle(el);
                        // Outgoing messages are typically right-aligned
                        return el.matches('.message-out') || style.textAlign === 'right' || style.justifyContent === 'flex-end';
                    });
                }
                if (!outgoing.length) return { ok: false, reason: 'no_outgoing' };

                // Get the last outgoing message
                const last = outgoing[outgoing.length - 1];
                const textEl = last.closest('[data-testid="msg-container"]') || last;
                const text = textEl ? (textEl.innerText || '').trim() : '';

                const hasClock = textEl && textEl.querySelector(
                    'span[data-icon="clock"], ' +
                    '[data-icon="clock"]'
                );

                return {
                    ok: text.includes(expected.substring(0, 30)),
                    has_clock: !!hasClock,
                    snippet: text.substring(0, 60),
                };
            }
            """, expected)
            if not result:
                return True  # Verification not possible — assume success
            if result.get("ok") and not result.get("has_clock"):
                return True
            if result.get("ok") and result.get("has_clock"):
                # Message is in DOM but still sending — wait briefly
                time.sleep(0.5)
                return True  # Optimistic; clock should clear shortly
            logger.debug(
                f"[Send] Verify failed: {result.get('reason', 'mismatch')} "
                f"snippet={result.get('snippet', '')!r}"
            )
            return False
        except Exception as e:
            logger.debug(f"[Send] Verify error (non-fatal): {e}")
            return True  # Don't fail sends due to verify errors

    def _verify_last_image_sent(self, page) -> bool:
        """Verify the last outgoing message was an image (no clock icon)."""
        try:
            result = page.evaluate("""
            () => {
                let outgoing = document.querySelectorAll(
                    'div[data-testid="msg-container"].message-out'
                );
                if (!outgoing.length) {
                    outgoing = document.querySelectorAll('div.message-out');
                }
                if (!outgoing.length) return { ok: false, reason: 'no_outgoing' };
                const last = outgoing[outgoing.length - 1];
                const hasImage = last.querySelector(
                    'img, canvas, [data-testid="image-thumb"], ' +
                    '[data-testid="media-msg"], ' +
                    'div[style*="background-image"]'
                );
                const hasClock = last.querySelector(
                    '[data-icon="clock"]'
                );
                return {
                    ok: !!hasImage,
                    has_clock: !!hasClock,
                };
            }
            """)
            if not result:
                return True
            if result.get("ok") and not result.get("has_clock"):
                return True
            if result.get("ok") and result.get("has_clock"):
                time.sleep(0.5)
                return True
            logger.debug(f"[Send] Image verify failed: {result.get('reason', 'no_image')}")
            return False
        except Exception as e:
            logger.debug(f"[Send] Image verify error (non-fatal): {e}")
            return True


# Singleton
sender = MessageSender()
