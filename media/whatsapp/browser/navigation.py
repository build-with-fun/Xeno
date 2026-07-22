"""WhatsApp chat navigation: open, close, search.

Fixes the original code's issues:
- `open_chat` only matched by name substring (could open wrong contact)
- Fallback to search bar used fragile selectors
- No verification that the chat actually opened
"""
from __future__ import annotations

import time
from typing import Optional

from media.whatsapp.browser.wpp import wpp
from media.whatsapp.core.exceptions import BrowserError, NonReplyableError
from media.whatsapp.human.behavior import human
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

# Robust selectors for the message input box (tried in order)
INPUT_SELECTORS = [
    'div[contenteditable="true"][data-tab="10"]',
    'div[contenteditable="true"][role="textbox"]',
    'footer div[contenteditable="true"]',
    'div[aria-placeholder*="message" i]',
    'div[title="Type a message"]',
    'div[aria-label="Type a message"]',
    'div[data-testid="conversation-compose-box-input"]',
    'div[contenteditable="true"]',
]


class Navigation:
    """Chat open/close operations."""

    @staticmethod
    def _chat_can_reply(jid: str) -> bool:
        """Check if a chat type supports replies based on JID suffix."""
        if not jid:
            return True
        if "@broadcast" in jid or "@newsletter" in jid:
            return False
        return True

    @staticmethod
    def _is_non_replyable_chat(page) -> bool:
        """Check if the currently open chat has no input box (announcement group, etc.).

        Key insight: if there are ZERO [contenteditable] elements on the entire page
        while a chat is supposedly open, the chat has no input box — it's non-replyable.
        """
        try:
            result = page.evaluate("""
            () => {
                const edits = document.querySelectorAll('[contenteditable="true"]');
                // Have contenteditable — can reply
                if (edits.length > 0) return { nonReplyable: false, reason: 'has_input', count: edits.length };

                // No contenteditable at all — chat is non-replyable (announcement group, broadcast, etc.)
                // Also check header text for diagnostics
                const header = document.querySelector(
                    'header[data-testid="conversation-header"], ' +
                    'header div[data-testid="conversation-info-header"], ' +
                    '#main header'
                );
                const headerText = header ? (header.innerText || '').trim() : '';
                const hasAnnouncementText = /announcement|broadcast|newsletter/i.test(headerText);
                return {
                    nonReplyable: true,
                    reason: 'no_input_box',
                    headerText: headerText.slice(0, 100),
                    hasAnnouncementText,
                };
            }
            """)
            if result and result.get("nonReplyable"):
                logger.warning(f"[Nav] Chat is non-replyable: {result.get('reason')} "
                              f"(header: {result.get('headerText','?')!r})")
                return True
            return False
        except Exception:
            return False

    def open_chat(self, page, contact: str, jid: str = "") -> bool:
        """Open a chat. `jid` is the WPP chat ID (_serialized) for direct open.

        Returns True if the chat is open and ready for input.
        """
        human.pre_open_pause()

        if jid and not self._chat_can_reply(jid):
            raise NonReplyableError(f"{contact} ({jid}) is a broadcast/newsletter")

        # Method 1: Direct JID open (most reliable when we have the JID)
        if jid:
            if self._open_via_wpp_jid(page, jid):
                if self._verify_chat_open(page):
                    return True
                if self._is_non_replyable_chat(page):
                    raise NonReplyableError(f"{contact} ({jid}) is a non-replyable chat")
                logger.debug(f"[Nav] Direct JID open succeeded but verify failed for {contact}")

        # Method 2: Sidebar click
        if self.open_chat_by_sidebar_click(page, contact):
            if self._verify_chat_open(page):
                return True
            if self._is_non_replyable_chat(page):
                raise NonReplyableError(f"{contact} is a non-replyable chat")
            logger.debug(f"[Nav] Sidebar click succeeded but verify failed for {contact}")

        # Method 3: WPP name-based
        if self._open_via_wpp(page, contact):
            if self._verify_chat_open(page):
                return True
            if self._is_non_replyable_chat(page):
                raise NonReplyableError(f"{contact} is a non-replyable chat")
            logger.debug(f"[Nav] WPP open succeeded but verify failed for {contact}")

        # Method 4: Search bar
        if self._open_via_search(page, contact):
            if self._verify_chat_open(page):
                return True

        logger.error(f"[Nav] Could not open chat for {contact}")
        return False

    def _open_via_wpp_jid(self, page, jid: str) -> bool:
        """Open a chat directly by JID using WPP.chat.openChatBottom."""
        if not jid:
            return False
        try:
            result = page.evaluate("""
            async (chatId) => {
                try {
                    await WPP.chat.openChatBottom(chatId);
                    return { success: true };
                } catch(e) {
                    return { success: false, error: String(e) };
                }
            }
            """, jid)
            if result and result.get("success"):
                logger.warning(f"[Nav] Direct JID open: {jid}")
                return True
            logger.debug(f"[Nav] Direct JID open failed for {jid}: {result}")
            return False
        except Exception as e:
            logger.warning(f"[Nav] Direct JID open error: {e}")
            return False

    def close_chat(self, page) -> None:
        """Close the current chat (press Escape twice)."""
        try:
            for _ in range(2):
                page.keyboard.press("Escape")
                time.sleep(0.1)
        except Exception as e:
            logger.debug(f"[Nav] close_chat error (non-fatal): {e}")

    def _open_via_wpp(self, page, contact: str) -> bool:
        """Use WPP.whatsapp.ChatStore + openChatBottom."""
        try:
            result = page.evaluate("""
            async (name) => {
                try {
                    const lower = name.toLowerCase().trim();
                    const store = window.WPP?.whatsapp?.ChatStore;
                    if (!store) return { success: false, reason: 'no_chatstore' };
                    const models = store.getModelsArray();
                    if (!models || !models.length) return { success: false, reason: 'no_chats', count: 0 };

                    // Try exact match first, then partial
                    const allNames = [];
                    let chat = null;
                    for (const c of models) {
                        const n = (c.name || c.pushname || c.formattedTitle || c.id?.user || '').toLowerCase().trim();
                        allNames.push(n);
                        if (n === lower) { chat = c; break; }
                    }
                    if (!chat) {
                        for (const c of models) {
                            const n = (c.name || c.pushname || c.formattedTitle || c.id?.user || '').toLowerCase().trim();
                            if (n.includes(lower) || lower.includes(n)) { chat = c; break; }
                        }
                    }
                    if (!chat) {
                        return {
                            success: false, reason: 'not_found',
                            total: models.length,
                            names: allNames.filter(Boolean).slice(0, 15),
                        };
                    }
                    await WPP.chat.openChatBottom(chat.id._serialized);
                    return { success: true, chatId: chat.id._serialized, name: chat.name || chat.pushname || '' };
                } catch(e) {
                    return { success: false, reason: String(e) };
                }
            }
            """, contact)
            if result and result.get("success"):
                logger.warning(f"[Nav] WPP opened chat '{result.get('name','?')}' ({result.get('chatId','?')})")
                return True
            reason = result.get("reason") if result else "no_result"
            total = result.get("total", '?') if result else '?'
            names = result.get("names", []) if result else []
            logger.warning(f"[Nav] WPP open failed for '{contact}': {reason} (total chats: {total}) — names: {names}")
            return False
        except Exception as e:
            logger.warning(f"[Nav] WPP open error for {contact}: {e}")
            return False

    def _open_via_search(self, page, contact: str) -> bool:
        """Fallback: use the search bar."""
        try:
            page.keyboard.press("Escape")
            time.sleep(0.2)
            # Try multiple search-box selectors (expanded for 2026 WhatsApp)
            search = (
                page.query_selector('div[data-testid="search-input"]')
                or page.query_selector('div[contenteditable="true"][data-tab="3"]')
                or page.query_selector('div[role="textbox"][contenteditable="true"]')
                or page.query_selector('div[aria-label="Search text input"]')
                or page.query_selector('div[aria-label="Search"]')
                or page.query_selector('div[title="Search"]')
                or page.query_selector('[data-testid="chat-list-search"] input')
                or page.query_selector('[data-testid="search"] input')
                or page.query_selector('input[type="text"]')
            )
            if not search:
                logger.warning("[Nav] No search input found")
                return False
            search.click()
            time.sleep(0.2)
            # Clear any existing search text
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
            time.sleep(0.1)
            page.keyboard.type(contact, delay=30)
            time.sleep(0.8)
            # Click first result (use up-to-date selectors)
            first = (
                page.query_selector('[data-testid="cell-frame-container"]')
                or page.query_selector('div[role="listitem"]')
                or page.query_selector('[data-testid="conversation-info-row"]')
            )
            if first:
                first.click()
                page.keyboard.press("Escape")
                return True
            logger.debug(f"[Nav] No search results for {contact}")
            page.keyboard.press("Escape")
            return False
        except Exception as e:
            logger.warning(f"[Nav] Search fallback error for {contact}: {e}")
            return False

    def _verify_chat_open(self, page, timeout: float = 3.0) -> bool:
        """Poll for the input box with timeout. Returns True when found."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for sel in INPUT_SELECTORS:
                try:
                    el = page.query_selector(sel)
                    if el:
                        return True
                except Exception:
                    continue
            time.sleep(0.2)

        # Quick check: no contenteditable anywhere on the page at all?
        try:
            has_any_editable = page.evaluate("() => !!document.querySelector('[contenteditable=\"true\"]')")
            if has_any_editable is False:
                logger.warning("[Nav] No contenteditable elements on entire page — chat has no input box")
                return False
        except Exception:
            pass

        try:
            diag = page.evaluate("""
            () => {
                const chatHeader = document.querySelector(
                    'header[data-testid="conversation-header"], ' +
                    'header div[data-testid="conversation-info-header"], ' +
                    '#main header'
                );
                const headerText = chatHeader ? (chatHeader.innerText || '').trim().slice(0, 120) : 'NO_HEADER';

                const footer = document.querySelector('footer, div[data-testid="conversation-footer"]');
                const footerHTML = footer ? footer.outerHTML.slice(0, 300) : 'NO_FOOTER';

                const edits = Array.from(document.querySelectorAll('[contenteditable="true"]'));
                const editInfo = edits.map(el => ({
                    tag: el.tagName,
                    tabIndex: el.getAttribute('data-tab') || '',
                    role: el.getAttribute('role') || '',
                    parent: (el.parentElement?.className || '').slice(0, 60),
                    visible: el.offsetParent !== null,
                    placeholder: el.getAttribute('aria-placeholder') || el.getAttribute('aria-label') || '',
                    text: (el.innerText || '').slice(0, 60),
                }));

                const blockedBanner = document.querySelector('[data-testid="blocked-banner"], .blocked-banner');
                const archivedLabel = document.querySelector('[data-testid="archived-label"], .archived-label');

                // Check if header says "Announcements" (group with only-admin posting)
                const isAnnouncement = /announcement/i.test(headerText);

                return {
                    header: headerText,
                    blocked: blockedBanner ? (blockedBanner.innerText || '').trim() : null,
                    archived: archivedLabel ? (archivedLabel.innerText || '').trim() : null,
                    contenteditable_count: editInfo.length,
                    contenteditable_elements: editInfo,
                    footer_snippet: footerHTML,
                    url: window.location.href,
                    is_announcement: isAnnouncement,
                };
            }
            """)
            if diag:
                logger.warning(f"[Nav] Verify failed: header='{diag.get('header','?')}' blocked={diag.get('blocked')} archived={diag.get('archived')} editableElements={diag.get('contenteditable_elements',[])} announcement={diag.get('is_announcement')} url={diag.get('url','')}")
                if diag.get('blocked') or diag.get('archived'):
                    logger.warning(f"[Nav] Chat is blocked or archived — no input box expected")
                if diag.get('is_announcement'):
                    logger.warning(f"[Nav] Chat is an announcement-only group — cannot reply")
        except Exception as e:
            logger.warning(f"[Nav] Verify diagnostic error: {e}")
        return False

    def open_chat_by_sidebar_click(self, page, contact: str) -> bool:
        """Click on the sidebar chat row by matching contact name.

        More reliable than search/WPP for opening chats since it uses
        the same DOM the scanner already found the contact in.

        Research notes (July 2026):
        - WhatsApp Web chat list items use updated CSS classes: ._amk3 (name), ._amk4 (preview)
        - data-testid attributes are generally more stable; prefer [data-testid="cell-frame-title"]
        - Fall back to [data-testid="conversation-info-header"] for alternative layouts
        """
        try:
            result = page.evaluate("""
            (name) => {
                const lower = name.toLowerCase().trim();
                const items = document.querySelectorAll(
                    '[data-testid="cell-frame-container"], ' +
                    'div[role="listitem"], ' +
                    '[data-testid="conversation-info-row"]'
                );
                const totalItems = items.length;
                if (!totalItems) return {found: false, reason: 'no_items', total: 0, names: []};

                // Helper to extract name from chat item
                function getName(el) {
                    const selectors = [
                        '[data-testid="cell-frame-title"] span',
                        'span[title]:not([title=""]):not([data-testid])',
                        '._amk3',           // 2026 WhatsApp Web class
                        'div[role="heading"] span',
                        '[data-testid="conversation-info-header"] span',
                    ];
                    for (const sel of selectors) {
                        const elm = el.querySelector(sel);
                        if (elm) {
                            const n = elm.getAttribute('title') || elm.innerText || '';
                            if (n.trim()) return n.trim();
                        }
                    }
                    return '';
                }
                // Get all visible names for diagnostic
                const allNames = Array.from(items).map(el => getName(el)).filter(Boolean);

                // Exact match first
                for (const el of items) {
                    const elName = getName(el);
                    const elLower = elName.toLowerCase();
                    if (elLower === lower || elLower.replace(/\\s/g, '') === lower.replace(/\\s/g, '')) {
                        el.click();
                        return {found: true, method: 'exact', name: elName};
                    }
                }
                // Partial match
                for (const el of items) {
                    const elName = getName(el);
                    const elLower = elName.toLowerCase();
                    if (elLower.includes(lower) || lower.includes(elLower)) {
                        el.click();
                        return {found: true, method: 'partial', name: elName};
                    }
                }
                return {found: false, reason: 'no_match', total: totalItems, names: allNames.slice(0, 20)};
            }
            """, contact)
            if result and result.get("found"):
                logger.warning(f"[Nav] Sidebar click matched '{result.get('name','?')}' via {result.get('method','?')}")
                return True
            reason = result.get("reason") if result else "no_result"
            diag_names = result.get("names", []) if result else []
            logger.warning(f"[Nav] Sidebar click failed for '{contact}': {reason} (chats in DOM: {result.get('total',0) if result else '?'}) — visible names: {diag_names}")
            return False
        except Exception as e:
            logger.warning(f"[Nav] Sidebar click error for {contact}: {e}")
            return False

    def find_input_box(self, page):
        """Return the input box element, or None."""
        for sel in INPUT_SELECTORS:
            try:
                el = page.query_selector(sel)
                if el:
                    return el
            except Exception:
                continue
        return None

    def mark_chat_read(self, page, jid: str) -> bool:
        """Mark chat as read via WPP.js.
        
        Tries multiple methods: sendSeen, markUnreadAsRead, fallback to
        directly setting unreadCount on the ChatStore model.
        """
        try:
            result = page.evaluate("""
            (jid) => {
                // Method 1: sendSeen (most standard)
                if (window.WPP && window.WPP.chat && window.WPP.chat.sendSeen) {
                    window.WPP.chat.sendSeen(jid);
                    return 'sendSeen';
                }
                // Method 2: markUnreadAsRead
                if (window.WPP && window.WPP.chat && window.WPP.chat.markUnreadAsRead) {
                    window.WPP.chat.markUnreadAsRead(jid);
                    return 'markUnreadAsRead';
                }
                // Method 3: direct ChatStore manipulation
                if (window.WPP && window.WPP.whatsapp && window.WPP.whatsapp.ChatStore) {
                    const model = window.WPP.whatsapp.ChatStore.get(jid);
                    if (model) {
                        // Try both direct and getter-based approaches
                        model.unreadCount = 0;
                        if (typeof model.set === 'function') {
                            model.set('unreadCount', 0);
                            model.set('__x_unreadCount', 0);
                        }
                        if (typeof model.trigger === 'function') {
                            model.trigger('change:unreadCount');
                        }
                        return 'chatstore_direct';
                    }
                }
                return 'none';
            }
            """, jid)
            if result and result != 'none':
                logger.info(f"[Nav] Marked chat {jid[:20]}... as read via {result}")
                return True
            logger.warning(f"[Nav] No WPP mark-read method available for {jid[:20]}...")
        except Exception as e:
            logger.warning(f"[Nav] mark_chat_read failed for {jid[:20]}...: {e}")
        return False



# Singleton
navigation = Navigation()
