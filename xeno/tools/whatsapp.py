"""WhatsApp tools — send messages, check status, manage contacts via the WhatsApp bot API."""

from __future__ import annotations

import os
import json
from typing import Optional

import httpx

WHATSAPP_API_BASE = os.environ.get("WHATSAPP_API_BASE", "http://127.0.0.1:5000")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if WHATSAPP_API_TOKEN:
        h["Authorization"] = f"Bearer {WHATSAPP_API_TOKEN}"
    return h


def whatsapp_send(contact: str, message: str, delay_seconds: int = 0) -> str:
    """Send a WhatsApp message to a contact.

    Args:
        contact: Contact name or phone number (e.g. "Mom", "+923001234567")
        message: The text message to send
        delay_seconds: Delay before sending (0 = immediate)

    Returns:
        Confirmation of the message sent or error details.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{WHATSAPP_API_BASE}/api/outbound/send",
                json={"contact": contact, "text": message, "delay_seconds": delay_seconds},
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                return f"Message sent to {contact}: {message[:80]}"
            elif resp.status_code == 503:
                return (
                    "WhatsApp bot is not running. Start it with: "
                    f"cd media/whatsapp && python main.py"
                )
            else:
                return f"Failed to send: HTTP {resp.status_code} — {resp.text[:200]}"
    except httpx.ConnectError:
        return (
            f"Cannot connect to WhatsApp bot at {WHATSAPP_API_BASE}. "
            "Make sure the bot is running: cd media/whatsapp && python main.py"
        )
    except Exception as e:
        return f"Error sending WhatsApp message: {e}"


def whatsapp_status() -> str:
    """Check if the WhatsApp bot is running and healthy.

    Returns:
        Status info including uptime, pending messages, and bot health.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{WHATSAPP_API_BASE}/api/health", headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                return f"WhatsApp bot is running. Status: {status}"
            return f"WhatsApp bot responded with HTTP {resp.status_code}"
    except httpx.ConnectError:
        return (
            f"WhatsApp bot is NOT running at {WHATSAPP_API_BASE}. "
            "Start it with: cd media/whatsapp && python main.py"
        )
    except Exception as e:
        return f"Error checking WhatsApp status: {e}"


def whatsapp_pending() -> str:
    """List pending messages awaiting approval in the WhatsApp bot.

    Returns:
        List of pending messages or status info.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{WHATSAPP_API_BASE}/api/pending", headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", data if isinstance(data, list) else [])
                if not items:
                    return "No pending messages awaiting approval."
                lines = []
                for item in items[:10]:
                    contact = item.get("contact", "?")
                    text = item.get("text", "")[:60]
                    lines.append(f"  - {contact}: {text}")
                return f"Pending messages ({len(items)}):\n" + "\n".join(lines)
            return f"Failed to get pending: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error getting pending messages: {e}"


def whatsapp_schedule(contact: str, message: str, scheduled_for: str) -> str:
    """Schedule a WhatsApp message for a specific datetime.

    Args:
        contact: Contact name or phone number
        message: The text message to send
        scheduled_for: ISO 8601 datetime string (e.g. "2026-07-15T14:30:00")

    Returns:
        Confirmation of the scheduled message.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{WHATSAPP_API_BASE}/api/outbound/schedule",
                json={
                    "contact": contact,
                    "text": message,
                    "scheduled_for": scheduled_for,
                },
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                msg_id = data.get("id", "?")
                return f"Message scheduled for {contact} at {scheduled_for} (id: {msg_id})"
            elif resp.status_code == 503:
                return "WhatsApp bot is not running."
            else:
                return f"Failed to schedule: HTTP {resp.status_code} — {resp.text[:200]}"
    except httpx.ConnectError:
        return f"Cannot connect to WhatsApp bot at {WHATSAPP_API_BASE}."
    except Exception as e:
        return f"Error scheduling message: {e}"


def whatsapp_metrics() -> str:
    """Get WhatsApp bot metrics — messages sent, received, errors, etc.

    Returns:
        Metrics summary.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{WHATSAPP_API_BASE}/api/metrics", headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                counters = data.get("counters", {})
                gauges = data.get("gauges", {})
                lines = []
                for k, v in counters.items():
                    lines.append(f"  {k}: {v}")
                for k, v in gauges.items():
                    lines.append(f"  {k}: {v}")
                return "WhatsApp metrics:\n" + "\n".join(lines) if lines else "No metrics available."
            return f"Failed to get metrics: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error getting metrics: {e}"


async def whatsapp_web_check() -> str:
    """Open WhatsApp Web in the browser, wait for it to load, check if logged in,
    and take a screenshot. Returns the page status and screenshot path."""
    try:
        from xeno.tools.browser import _get_page
        page = await _get_page()
        await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        title = await page.title()
        url = page.url

        result = f"Opened WhatsApp Web\nTitle: {title}\nURL: {url}\n"

        page_text = await page.inner_text("body")
        page_text = page_text[:2000]

        if "QR" in page_text or "Scan" in page_text or "scan" in page_text:
            result += "Status: QR code visible — scan with your phone to log in.\n"
        elif "Chats" in page_text or "Search" in page_text or "message" in page_text.lower():
            result += "Status: Already logged in. Messages detected.\n"
        else:
            result += "Status: Page loaded, checking content.\n"

        import time
        from xeno.config import XenoConfig
        config = XenoConfig.from_env()
        shot_dir = config.data_dir / "browser_screenshots"
        shot_dir.mkdir(parents=True, exist_ok=True)
        path = shot_dir / f"whatsapp_{int(time.time())}.png"
        await page.screenshot(path=str(path), full_page=True)
        result += f"Screenshot saved: {path}\n"
        result += f"Page content:\n{page_text[:1500]}"

        return result
    except Exception as e:
        return f"Error checking WhatsApp Web: {e}"


# ── Read tools ─────────────────────────────────────────────────────────────

def whatsapp_list_contacts(limit: int = 100, offset: int = 0) -> str:
    """List WhatsApp contacts/chats from the bot's database.

    Args:
        limit: Max contacts to return (default 100, max 500)
        offset: Pagination offset

    Returns:
        Formatted list of contacts with name, phone, unread count, last seen.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{WHATSAPP_API_BASE}/api/contacts",
                params={"limit": min(limit, 500), "offset": max(offset, 0)},
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                contacts = data.get("contacts", [])
                if not contacts:
                    return "No contacts found in WhatsApp database."
                lines = [f"Contacts ({data.get('count', len(contacts))}):"]
                for c in contacts:
                    name = c.get("name", "?")
                    phone = c.get("phone", "")
                    msgs = c.get("total_messages", 0)
                    last = c.get("last_seen", "")[:19]
                    tags = ", ".join(c.get("tags", []))
                    tag_str = f" [{tags}]" if tags else ""
                    lines.append(f"  {name}{tag_str} | {phone} | {msgs} msgs | last: {last}")
                return "\n".join(lines)
            return f"Failed to list contacts: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error listing contacts: {e}"


def whatsapp_search_contacts(query: str) -> str:
    """Search WhatsApp contacts by name.

    Args:
        query: Name or partial name to search for

    Returns:
        Matching contacts with details.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{WHATSAPP_API_BASE}/api/contacts/search",
                params={"q": query},
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                contacts = data.get("contacts", [])
                if not contacts:
                    return f"No contacts matching '{query}'."
                lines = [f"Contacts matching '{query}' ({data.get('count', len(contacts))}):"]
                for c in contacts:
                    name = c.get("name", "?")
                    phone = c.get("phone", "")
                    msgs = c.get("total_messages", 0)
                    tags = ", ".join(c.get("tags", []))
                    tag_str = f" [{tags}]" if tags else ""
                    lines.append(f"  {name}{tag_str} | {phone} | {msgs} msgs")
                return "\n".join(lines)
            return f"Failed to search contacts: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error searching contacts: {e}"


def whatsapp_get_contact(name: str) -> str:
    """Get detailed info about a specific WhatsApp contact.

    Args:
        name: Contact name exactly as stored

    Returns:
        Contact details including tags, stats, sentiment.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{WHATSAPP_API_BASE}/api/contacts/{httpx.utils.quote(name, safe='')}",
                headers=_headers(),
            )
            if resp.status_code == 200:
                c = resp.json()
                lines = [
                    f"Contact: {c.get('name', '?')}",
                    f"  Phone: {c.get('phone', '')}",
                    f"  Tags: {', '.join(c.get('tags', [])) or '(none)'}",
                    f"  Group: {'Yes' if c.get('is_group') else 'No'}",
                    f"  Blocked: {'Yes' if c.get('is_blocked') else 'No'}",
                    f"  Messages: {c.get('total_messages', 0)}",
                    f"  Replies: {c.get('total_replies', 0)}",
                    f"  Last seen: {c.get('last_seen', '')[:19]}",
                    f"  Sentiment: {c.get('sentiment_score', 0):.2f}",
                ]
                return "\n".join(lines)
            elif resp.status_code == 404:
                return f"Contact '{name}' not found."
            return f"Failed to get contact: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error getting contact: {e}"


def whatsapp_get_chat_history(contact_name: str, limit: int = 50) -> str:
    """Get chat history with a specific WhatsApp contact from the bot's database.

    Args:
        contact_name: Contact name exactly as stored
        limit: Max messages to return (default 50, max 500)

    Returns:
        Formatted chat history with timestamps and message content.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{WHATSAPP_API_BASE}/api/messages/{httpx.utils.quote(contact_name, safe='')}",
                params={"limit": min(limit, 500)},
                headers=_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                msgs = data.get("messages", [])
                if not msgs:
                    return f"No chat history with '{contact_name}'."
                lines = [f"Chat history with {contact_name} ({len(msgs)} messages):"]
                for m in msgs:
                    role = m.get("role", "?")
                    kind = m.get("kind", "text")
                    ts = m.get("created_at", "")[11:19]
                    content = m.get("content", "")[:120]
                    label = f"[{kind.upper()}] " if kind != "text" else ""
                    icon = "→" if role == "assistant" else "←"
                    lines.append(f"  {ts} {icon} {label}{content}")
                return "\n".join(lines)
            elif resp.status_code == 404:
                return f"Contact '{contact_name}' not found."
            return f"Failed to get chat history: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error getting chat history: {e}"


def whatsapp_get_unread() -> str:
    """Get unread WhatsApp messages from the bot's live pending list.

    Returns:
        List of contacts with unread messages, previews, and message types.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{WHATSAPP_API_BASE}/api/unread", headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("unread", [])
                if not items:
                    return "No unread messages."
                lines = [f"Unread messages ({data.get('count', len(items))}):"]
                for item in items:
                    contact = item.get("contact", "?")
                    preview = item.get("preview", "")[:80]
                    mtype = item.get("mtype", "text")
                    lines.append(f"  {contact} [{mtype}]: {preview}")
                return "\n".join(lines)
            return f"Failed to get unread: HTTP {resp.status_code}"
    except httpx.ConnectError:
        return "WhatsApp bot is not running."
    except Exception as e:
        return f"Error getting unread: {e}"


WHATSAPP_TOOLS = [
    whatsapp_send,
    whatsapp_status,
    whatsapp_pending,
    whatsapp_schedule,
    whatsapp_metrics,
    whatsapp_web_check,
    whatsapp_list_contacts,
    whatsapp_search_contacts,
    whatsapp_get_contact,
    whatsapp_get_chat_history,
    whatsapp_get_unread,
]
