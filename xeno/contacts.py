"""Contact context provider — fetches WhatsApp + Gmail contacts for agent context."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_contact_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 30.0

WHATSAPP_API_BASE = os.environ.get("WHATSAPP_API_BASE", "http://127.0.0.1:5000")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")


def _whatsapp_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if WHATSAPP_API_TOKEN:
        h["Authorization"] = f"Bearer {WHATSAPP_API_TOKEN}"
    return h


def _get_whatsapp_contacts() -> str:
    """Fetch WhatsApp contacts from the bot's admin API."""
    import httpx
    lines: list[str] = []
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{WHATSAPP_API_BASE}/api/contacts",
                params={"limit": 200},
                headers=_whatsapp_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                contacts = data.get("contacts", [])
                if contacts:
                    for c in contacts[:50]:
                        name = c.get("name", "?")
                        phone = c.get("phone", "")
                        tags = c.get("tags", [])
                        msgs = c.get("total_messages", 0)
                        tag_str = f" [{', '.join(tags)}]" if tags else ""
                        lines.append(f"  {name}{tag_str} | {phone} | {msgs} msgs")
    except Exception:
        pass
    return "\n".join(lines)


def _get_email_contacts() -> str:
    """Fetch Gmail contacts/labels from the API."""
    lines: list[str] = []
    try:
        from xeno.tools.gmail import _get_gmail_service
        service = _get_gmail_service()
        if service:
            results = service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            for lbl in labels:
                name = lbl.get("name", "")
                if name and name not in ("CHAT", "SENT", "DRAFT", "STARRED", "IMPORTANT", "CATEGORY_PERSONAL", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS", "INBOX", "UNREAD", "TRASH", "SPAM"):
                    lines.append(f"  [Label] {name}")

            results = service.users().messages().list(
                userId="me", maxResults=50, q="in:inbox"
            ).execute()
            msgs = results.get("messages", [])
            senders: set[str] = set()
            for m in msgs[:30]:
                msg_data = service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From"]
                ).execute()
                for hdr in msg_data.get("payload", {}).get("headers", []):
                    if hdr.get("name") == "From":
                        senders.add(hdr.get("value", ""))
            for s in list(senders)[:20]:
                lines.append(f"  [Sender] {s}")
    except Exception:
        pass
    return "\n".join(lines)


def get_contact_context() -> str:
    """Get formatted contact context from WhatsApp + Gmail.

    Cached for 30 seconds. Returns empty string if nothing available.
    """
    now = time.time()

    whatskey = "whatsapp"
    if whatskey in _contact_cache:
        cached, ts = _contact_cache[whatskey]
        if now - ts < _CACHE_TTL:
            wa_ctx = cached
        else:
            wa_ctx = _get_whatsapp_contacts()
            _contact_cache[whatskey] = (wa_ctx, now)
    else:
        wa_ctx = _get_whatsapp_contacts()
        _contact_cache[whatskey] = (wa_ctx, now)

    emailkey = "email"
    if emailkey in _contact_cache:
        cached, ts = _contact_cache[emailkey]
        if now - ts < _CACHE_TTL:
            em_ctx = cached
        else:
            em_ctx = _get_email_contacts()
            _contact_cache[emailkey] = (em_ctx, now)
    else:
        em_ctx = _get_email_contacts()
        _contact_cache[emailkey] = (em_ctx, now)

    parts: list[str] = []
    if wa_ctx:
        parts.append("## WhatsApp Contacts\n" + wa_ctx)
    if em_ctx:
        parts.append("## Email Contacts / Senders\n" + em_ctx)
    return "\n\n".join(parts)
