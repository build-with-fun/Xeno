"""Email Always-On Agent — dual-mode: MCP server + standalone.

Gmail-based email handling. In MCP mode: Main Agent handles emails.
In Standalone mode: Agent processes inbox independently.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from xeno.always_on.base import AlwaysOnAgent, AgentConfig, AgentMode

logger = logging.getLogger(__name__)


class EmailAgent(AlwaysOnAgent):
    """Always-on email agent with dual-mode operation."""

    def __init__(self, config: AgentConfig):
        config.provider_type = "email"
        super().__init__(config)
        self._connected = False
        self._creds_path = Path("agents/gmail/credentials.json")
        self._token_path = Path("agents/gmail/token.json")

    async def connect(self) -> bool:
        if not self._creds_path.exists():
            logger.warning(f"Gmail credentials not found at {self._creds_path}")
            self._connected = False
            return False
        try:
            from xeno.tools.gmail import gmail_list
            result = gmail_list(max_results=1)
            self._connected = "API not available" not in str(result) and "not found" not in str(result)
            return self._connected
        except Exception as e:
            logger.warning(f"Email connect failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def handle_event(self, event_type: str, data: dict) -> str:
        if event_type == "send":
            to = data.get("to", "")
            subject = data.get("subject", "")
            body = data.get("body", "")
            try:
                from xeno.tools.gmail import gmail_send
                result = gmail_send(to, subject, body)
                self._temporal_kg.add_fact("email", f"sent_to_{to}", subject,
                                           source="mcp_call", metadata={"to": to, "subject": subject})
                return str(result)
            except Exception as e:
                return f"Error sending: {e}"

        elif event_type == "list":
            try:
                from xeno.tools.gmail import gmail_list
                result = gmail_list(max_results=data.get("max", 10))
                return str(result)
            except Exception as e:
                return f"Error listing: {e}"

        elif event_type == "read":
            try:
                from xeno.tools.gmail import gmail_read
                result = gmail_read(data.get("message_id", ""))
                return str(result)
            except Exception as e:
                return f"Error reading: {e}"

        return f"Unknown event type: {event_type}"

    async def run_iteration(self) -> dict:
        if not self._connected:
            await self.connect()
            if not self._connected:
                return {"status": "disconnected", "error": "Gmail not connected"}
        try:
            from xeno.tools.gmail import gmail_list, gmail_filter
            inbox = gmail_list(max_results=5)
            filtered = gmail_filter(days=1, max_results=10)
            self._temporal_kg.add_fact("email", "iteration_check", "ok",
                                       source="iteration")
            return {"status": "ok", "inbox_preview": str(inbox)[:200], "filtered": str(filtered)[:200]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_contacts(self) -> str:
        """Fetch email contacts/senders for the contact context system."""
        if not self._connected:
            return ""
        try:
            from xeno.tools.gmail import _get_gmail_service
            service = _get_gmail_service()
            if not service:
                return ""
            results = service.users().messages().list(
                userId="me", maxResults=30, q="in:inbox"
            ).execute()
            msgs = results.get("messages", [])
            senders: set[str] = set()
            for m in msgs[:20]:
                msg_data = service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From"]
                ).execute()
                for hdr in msg_data.get("payload", {}).get("headers", []):
                    if hdr.get("name") == "From":
                        senders.add(hdr.get("value", ""))
            lines = [f"  {s}" for s in sorted(senders)]
            return "\n".join(lines)
        except Exception:
            return ""

    async def _cleanup(self):
        await self.disconnect()


def create_email_agent(duration_hours: float = 0,
                        mode: AgentMode = AgentMode.DUAL) -> EmailAgent:
    """Factory function for Email agent."""
    config = AgentConfig(
        name="email",
        provider_type="email",
        mode=mode,
        duration_hours=duration_hours,
        schedule_interval_seconds=300,
    )
    return EmailAgent(config)
