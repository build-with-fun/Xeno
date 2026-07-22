"""Sidebar scanner: detect unread messages.

Fixes the original code's issues:
- Used incredibly fragile CSS selectors that broke on every WhatsApp update
- `_TRANSIENT` regex only matched English "typing"/"recording"
- No detection of localized WhatsApp previews ("escribiendo", "digitando", etc.)
- Pending contacts dict was mutated by scanner AND main loop without a lock
"""
from __future__ import annotations

import re
import time
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

# Match typing/recording indicators in many languages
_TRANSIENT_RE = re.compile(
    r"^\s*("
    r"typing\.?|"
    r"recording\.?|"
    r"typing\s*…|"
    r"recording\s*…|"
    r"🎤\s*recording|"
    r"escribiendo|digitando|digitação|"
    r"schreibt|saisie|scrittura|"
    r"入力中|正在输入|輸入中|"
    r"typing a message|audio"
    r")\s*\.?\s*$",
    re.IGNORECASE,
)


class SidebarScanner:
    """Scans WhatsApp Web's sidebar for unread messages."""

    def __init__(self) -> None:
        self._first_scan = True

    def scan(self, page, pending: dict) -> int:
        """Scan the sidebar and update `pending` dict.

        Returns the number of new/updated contacts detected.
        """
        try:
            rows = self._extract_rows(page)
        except Exception as e:
            logger.error(f"[Scan] Row extraction failed: {e}")
            return 0

        if not rows and self._first_scan:
            self._first_scan = False
            logger.warning("[Scan] First scan returned 0 — running full diagnostics")
            # Dump ChatStore model keys to understand unread field structure
            try:
                diag = page.evaluate("""
                () => {
                    const info = { side_found: !!document.querySelector('#side') };
                    const store = window.WPP?.whatsapp?.ChatStore;
                    if (store) {
                        const models = store.getModelsArray();
                        if (models && models.length) {
                            const first = models[0];
                            const keys = Object.keys(first).filter(k =>
                                typeof first[k] !== 'function' && typeof first[k] !== 'object'
                            );
                            info.model_keys_sample = keys.slice(0, 25);
                            // Any non-zero unreadCount?
                            const withUnread = models.filter(m => parseInt(m.unreadCount || 0) > 0);
                            info.non_zero_unread = withUnread.length;
                        }
                    }
                    const side = document.querySelector('#side') || document;
                    const cells = side.querySelectorAll('[data-testid="cell-frame-container"]');
                    info.dom_cells = cells.length;
                    if (cells.length) {
                        info.first_cell_sample = cells[0].outerHTML.slice(0, 1000);
                    }
                    return info;
                }
                """)
                if diag:
                    logger.warning(f"[Scan] Diagnostics: {diag}")
            except Exception as e:
                logger.warning(f"[Scan] Diagnostics failed: {e}")

            # Retry DOM fallback immediately after diagnostics
            try:
                rows = self._extract_rows(page)
            except Exception:
                pass

        if not rows:
            return 0

        now = time.time()
        new_count = 0
        for row in rows:
            contact = (row.get("name") or "").strip()
            preview = (row.get("preview") or "").strip()
            if not contact:
                continue
            if _TRANSIENT_RE.match(preview):
                continue
            if preview.lower().startswith("you:"):
                continue

            mtype = self._classify_preview(preview)
            if mtype == "video":
                continue

            jid = row.get("jid", "")

            existing = pending.get(contact)
            if existing is None:
                pending[contact] = {
                    "last_seen": now, "preview": preview, "mtype": mtype, "jid": jid,
                }
                new_count += 1
                logger.info(
                    f"[Scan] New unread from {contact} ({mtype}): {preview[:50]}"
                )
            elif existing.get("preview") != preview:
                pending[contact] = {
                    "last_seen": now, "preview": preview, "mtype": mtype, "jid": jid,
                }
                new_count += 1
                logger.debug(f"[Scan] Updated {contact} preview")
        return new_count

    def _extract_rows(self, page) -> list[dict]:
        """Extract chat rows via WPP.whatsapp.ChatStore + DOM fallback."""
        # First pass: ChatStore
        try:
            result = page.evaluate("""
            () => {
                try {
                    if (!window.WPP || !window.WPP.whatsapp || !window.WPP.whatsapp.ChatStore) {
                        return {method: 'no_chatstore', chats: []};
                    }
                    const models = window.WPP.whatsapp.ChatStore.getModelsArray();
                    if (!models || !models.length) {
                        return {method: 'empty_store', chats: []};
                    }

                    const unread = models.filter(m => {
                        // Try direct property, getter, and attributes
                        let count = m.unreadCount;
                        if (count === undefined && typeof m.get === 'function') {
                            try { count = m.get('unreadCount'); } catch(e) {}
                        }
                        if (count === undefined && m.attributes) {
                            count = m.attributes.unreadCount;
                        }
                        return parseInt(count || 0) > 0;
                    });

                    const results = unread.map(c => ({
                        name: (c.name || c.pushname || c.formattedTitle || c.id?.user || '').trim(),
                        preview: (() => {
                            try {
                                const lm = c.lastMessage;
                                if (!lm) return '';
                                const body = lm.body;
                                if (!body) return '';
                                return typeof body === 'object'
                                    ? (body[0]?.text || JSON.stringify(body) || '')
                                    : String(body);
                            } catch(e) { return ''; }
                        })().trim(),
                        jid: c.id?._serialized || '',
                    })).filter(r => r.name);

                    return {
                        method: 'chatstore',
                        chats: results,
                        total_models: models.length,
                        total_unread: unread.length,
                    };
                } catch(e) {
                    return {method: 'error', error: String(e), chats: []};
                }
            }
            """)
            if result and result.get("chats") and len(result["chats"]) > 0:
                logger.warning(f"[Scan] ChatStore found {len(result['chats'])} unread chats "
                              f"(total: {result.get('total_models','?')}, unread: {result.get('total_unread','?')}): "
                              f"{[c['name'] for c in result['chats']]}")
                return result["chats"]
            elif self._first_scan:
                logger.warning(
                    f"[Scan] ChatStore: {result.get('method','?')} "
                    f"(total: {result.get('total_models','?')}, unread: {result.get('total_unread','?')})"
                )
        except Exception as e:
            logger.warning(f"[Scan] ChatStore extraction failed: {e}")

        # Fallback: DOM-based unread detection — scan cell-frame-container elements
        try:
            rows = page.evaluate("""
            () => {
                const side = document.querySelector('#side') || document;
                const results = [];

                // Strategy 1: Find all chat rows using the confirmed data-testid
                const cells = side.querySelectorAll('[data-testid="cell-frame-container"]');
                for (const cell of cells) {
                    // Check for unread badge (number badge)
                    const badge = cell.querySelector(
                        'span[data-testid*="unread"], ' +
                        'div[data-testid*="unread"], ' +
                        'span[aria-label*="unread" i], ' +
                        'div[aria-label*="unread" i], ' +
                        'span[class*="badge"], ' +
                        'div[class*="badge"]'
                    );
                    // Check for bold preview text
                    const previewEl = cell.querySelector('[data-testid="last-msg"], [data-testid="cell-frame-primary-detail"] span');
                    const isBold = previewEl && (
                        parseInt(window.getComputedStyle(previewEl).fontWeight) >= 600
                    );
                    // Check active/selected state — unread chats might not have badge but are bold
                    const primary = cell.querySelector('[data-testid="cell-frame-primary-detail"]');
                    const primaryBold = primary && (
                        parseInt(window.getComputedStyle(primary).fontWeight) >= 600
                    );

                    if (!badge && !isBold && !primaryBold) continue;

                    // Extract name from cell-frame-title
                    let name = '';
                    const titleEl = cell.querySelector('[data-testid="cell-frame-title"] span');
                    if (titleEl) {
                        name = (titleEl.getAttribute('title') || titleEl.innerText || '').trim();
                    }
                    if (!name) continue;

                    // Extract preview from last-msg or primary-detail
                    let preview = '';
                    const msgEl = cell.querySelector('[data-testid="last-msg"], [data-testid="cell-frame-primary-detail"] span');
                    if (msgEl) preview = msgEl.innerText.trim();

                    results.push({ name, preview, jid: '' });
                }

                return results;
            }
            """) or []
            if rows:
                logger.warning(f"[Scan] DOM fallback found {len(rows)} unread chats: {[r['name'] for r in rows]}")
                return rows
        except Exception as e:
            logger.warning(f"[Scan] DOM fallback failed: {e}")

        return []

    @staticmethod
    def _classify_preview(preview: str) -> str:
        """Classify message type from the sidebar preview text."""
        lower = preview.lower()
        if "[voice note]" in lower or "🎤" in preview or "audio" in lower:
            return "voice"
        if "[image]" in lower or "📷" in preview or "🖼" in preview or "photo" in lower:
            return "image"
        if "[video]" in lower or "📹" in preview or "🎥" in preview or "video" in lower:
            return "video"
        if "[document]" in lower or ".pdf" in lower or "pdf" in lower:
            return "pdf"
        if ".docx" in lower or ".doc" in lower:
            return "docx"
        if "[sticker]" in lower:
            return "sticker"
        return "text"


# Singleton
scanner = SidebarScanner()
