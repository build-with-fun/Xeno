"""Gmail tools for the 24/7 Gmail agent — read, send, search, filter.

Uses the Google Gmail API. Requires credentials.json in agents/gmail/.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global auth — loaded once
_gmail_service = None
_credentials_path = Path("agents/gmail/credentials.json")
_token_path = Path("agents/gmail/token.json")


def _get_gmail_service():
    """Get or create the Gmail API service."""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("Gmail tools require: google-api-python-client, google-auth-oauthlib, google-auth-httplib2")
        logger.error("Install with: uv add google-api-python-client google-auth-oauthlib google-auth-httplib2")
        return None

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    try:
        creds = None
        if _token_path.exists():
            creds = Credentials.from_authorized_user_file(str(_token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not _credentials_path.exists():
                    logger.error(f"Gmail credentials not found at {_credentials_path}")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(str(_credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            _token_path.parent.mkdir(parents=True, exist_ok=True)
            _token_path.write_text(creds.to_json(), encoding="utf-8")

        _gmail_service = build("gmail", "v1", credentials=creds)
        return _gmail_service
    except Exception as e:
        logger.error(f"Failed to initialize Gmail service: {e}")
        return None


def gmail_list(max_results: int = 10, query: str = "") -> str:
    """List recent emails. query: optional Gmail search query (e.g. 'from:someone@example.com')."""
    service = _get_gmail_service()
    if not service:
        return "Gmail API not available. Check credentials."

    try:
        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return "No emails found."

        output = [f"Recent emails ({len(messages)}):"]
        filtered = 0
        for msg_data in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_data["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            sender = headers.get("From", "")
            if not _email_sender_matches_filter(sender):
                filtered += 1
                continue
            snippet = msg.get("snippet", "")[:80]
            output.append(f"  [{msg_data['id'][:12]}] From: {sender}")
            output.append(f"          Subject: {headers.get('Subject', '?')[:60]}")
            output.append(f"          {snippet}")
        if filtered:
            output.append(f"  ({filtered} emails hidden by sender filter)")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing emails: {e}"


def gmail_read(message_id: str) -> str:
    """Read a specific email by its ID."""
    service = _get_gmail_service()
    if not service:
        return "Gmail API not available."

    try:
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        payload = msg.get("payload", {})
        body_data = ""

        def _extract_text(part):
            if part.get("mimeType", "").startswith("text/plain"):
                data = part.get("body", {}).get("data", "")
                if data:
                    import base64
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")[:2000]
            for subpart in part.get("parts", []):
                result = _extract_text(subpart)
                if result:
                    return result
            return ""

        if payload.get("parts"):
            body_data = _extract_text(payload)
        elif payload.get("body", {}).get("data"):
            import base64
            body_data = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")[:2000]

        return (
            f"From: {headers.get('From', '?')}\n"
            f"Subject: {headers.get('Subject', '?')}\n"
            f"Date: {headers.get('Date', '?')}\n"
            f"---\n"
            f"{body_data or '(no text content)'}"
        )
    except Exception as e:
        return f"Error reading email: {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email. to: recipient email address."""
    service = _get_gmail_service()
    if not service:
        return "Gmail API not available."

    try:
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to} (id: {sent['id'][:12]})"
    except Exception as e:
        return f"Error sending email: {e}"


def gmail_search(query: str, max_results: int = 10) -> str:
    """Search emails with Gmail search syntax."""
    return gmail_list(max_results=max_results, query=query)


def gmail_filter(query: str = "", days: int = 7, max_results: int = 20) -> str:
    """Filter recent emails. Returns a categorized summary (important/spam/promotions)."""
    service = _get_gmail_service()
    if not service:
        return "Gmail API not available."

    try:
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y/%m/%d")
        q = f"after:{since}"
        if query:
            q += f" {query}"

        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=q
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return f"No emails in the last {days} days."

        important = []
        spam_like = []
        promotions = []
        other = []

        for msg_data in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_data["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date", "X-Google-Smtp-Source"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            sender = headers.get("From", "?")
            subject = headers.get("Subject", "?")[:60]
            snippet = msg.get("snippet", "")[:60]

            entry = f"  [{msg_data['id'][:12]}] {sender} — {subject}"
            sender_lower = sender.lower()

            if any(kw in sender_lower for kw in ["noreply", "no-reply", "newsletter", "unsubscribe"]):
                promotions.append(entry)
            elif any(kw in sender_lower for kw in ["spam", "marketing", "promo"]):
                spam_like.append(entry)
            elif any(kw in sender_lower for kw in ["@"]):
                important.append(entry)
            else:
                other.append(entry)

        lines = [f"Email summary (last {days}d, {len(messages)} total):"]
        if important:
            lines.append(f"\nImportant ({len(important)}):")
            lines.extend(important[:5])
        if promotions:
            lines.append(f"\nPromotions/Newsletters ({len(promotions)}):")
            lines.extend(promotions[:3])
        if spam_like:
            lines.append(f"\nSpam-like ({len(spam_like)}):")
            lines.extend(spam_like[:3])
        if other:
            lines.append(f"\nOther ({len(other)}):")
            lines.extend(other[:3])

        return "\n".join(lines)
    except Exception as e:
        return f"Error filtering emails: {e}"


def gmail_approve(message_id: str, action: str = "reply") -> str:
    """Mark an email for reply approval. Returns the message ID for tracking."""
    from xeno.context_bridge import AgentContextBridge
    from xeno.config import XenoConfig
    bridge = AgentContextBridge(XenoConfig.from_env().data_dir / "agent_context")
    email_info = gmail_read(message_id)
    bridge.add_entry(
        "gmail",
        "approval_needed",
        f"Email {message_id} needs {action} approval",
        detail=email_info[:500],
        needs_approval=True,
    )
    return f"Email {message_id} queued for approval (action: {action}). Use agent_context_approve to approve."


# ── Email Filter (allowlist/blocklist) ────────────────────────────────────
# Persisted to agents/gmail/filter.json. Controls which senders the agent
# surfaces. "ans all emails from doctor radif" → allowlist.
# "ans all emails except of tem" → blocklist.

_FILTER_PATH = Path("agents/gmail/filter.json")
_FILTER_MODE_ALL = "all"
_FILTER_MODE_ALLOWLIST = "allowlist"
_FILTER_MODE_BLOCKLIST = "blocklist"

_EMAIL_FILTER_CACHE: dict = {}
_EMAIL_FILTER_MTIME: float = 0


def _email_filter_load() -> dict:
    global _EMAIL_FILTER_CACHE, _EMAIL_FILTER_MTIME
    try:
        mtime = _FILTER_PATH.stat().st_mtime if _FILTER_PATH.exists() else 0
        if mtime > _EMAIL_FILTER_MTIME:
            data = json.loads(_FILTER_PATH.read_text(encoding="utf-8"))
            _EMAIL_FILTER_CACHE = data
            _EMAIL_FILTER_MTIME = mtime
    except Exception:
        _EMAIL_FILTER_CACHE = {"mode": _FILTER_MODE_ALL, "contacts": []}
    return _EMAIL_FILTER_CACHE


def email_filter_set(mode: str, contacts: Optional[list[str]] = None) -> str:
    """Set email sender filter.
    
    Modes:
      "all"       — show emails from all senders.
      "allowlist" — ONLY show emails from the specified senders.
      "blocklist" — show emails from ALL senders EXCEPT these.
    """
    mode = mode.lower().strip()
    if mode not in (_FILTER_MODE_ALL, _FILTER_MODE_ALLOWLIST, _FILTER_MODE_BLOCKLIST):
        return f"Invalid mode '{mode}'. Use: all, allowlist, or blocklist."

    clist = [c.strip() for c in (contacts or []) if c.strip()]
    data = {"mode": mode, "contacts": clist}
    try:
        _FILTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FILTER_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        return f"Failed to save filter: {e}"

    global _EMAIL_FILTER_CACHE, _EMAIL_FILTER_MTIME
    _EMAIL_FILTER_CACHE = data
    _EMAIL_FILTER_MTIME = time.time()

    if mode == _FILTER_MODE_ALL:
        return "Email filter: showing emails from ALL senders."
    elif mode == _FILTER_MODE_ALLOWLIST:
        names = ", ".join(clist) if clist else "(none)"
        return f"Email filter: ONLY showing emails from: {names}"
    else:
        names = ", ".join(clist) if clist else "(none)"
        return f"Email filter: showing emails from EVERYONE except: {names}"


def email_filter_get() -> str:
    """Get the current email filter settings."""
    data = _email_filter_load()
    mode = data.get("mode", _FILTER_MODE_ALL)
    contacts = data.get("contacts", [])
    if mode == _FILTER_MODE_ALL:
        return "Email filter: showing emails from ALL senders."
    elif mode == _FILTER_MODE_ALLOWLIST:
        return f"Email filter: ONLY showing emails from: {', '.join(contacts) if contacts else '(none)'}"
    else:
        return f"Email filter: showing emails from EVERYONE except: {', '.join(contacts) if contacts else '(none)'}"


def _email_sender_matches_filter(from_header: str) -> bool:
    """Check whether an email's From header passes the current filter."""
    data = _email_filter_load()
    mode = data.get("mode", _FILTER_MODE_ALL)
    if mode == _FILTER_MODE_ALL:
        return True

    contacts = [c.lower().strip() for c in data.get("contacts", [])]
    sender = from_header.lower().strip()

    if mode == _FILTER_MODE_ALLOWLIST:
        return any(c in sender for c in contacts)

    if mode == _FILTER_MODE_BLOCKLIST:
        return not any(c in sender for c in contacts)

    return True
