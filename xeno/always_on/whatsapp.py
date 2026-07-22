"""WhatsApp Always-On Agent — dual-mode: MCP server + standalone.

WhatsApp provider is Baileys-based (via media/whatsapp/).
Auto-starts the bot if not running — zero manual setup needed.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from xeno.always_on.base import AlwaysOnAgent, AgentConfig, AgentMode

logger = logging.getLogger(__name__)


class WhatsAppAgent(AlwaysOnAgent):
    """Always-on WhatsApp agent with dual-mode operation."""

    def __init__(self, config: AgentConfig):
        config.provider_type = "whatsapp"
        super().__init__(config)
        self._connected = False
        self._auto_start_attempted = False

    async def connect(self) -> bool:
        try:
            from xeno.tools.whatsapp import whatsapp_status
            status = whatsapp_status()
            if "not started" in str(status).lower() or "has not been started" in str(status).lower():
                # Auto-start the bot if not running
                return await self._auto_start_bot()
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"WhatsApp connect failed: {e}")
            self._connected = False
            return False

    async def _auto_start_bot(self) -> bool:
        if self._auto_start_attempted:
            logger.info("WhatsApp auto-start already attempted this session — not retrying")
            return False
        self._auto_start_attempted = True
        try:
            logger.info("WhatsApp bot not running — auto-starting...")
            from xeno.tools.registry import whatsapp_start_bot
            result = await whatsapp_start_bot()
            if "failed" in result.lower() and "already running" not in result.lower():
                logger.warning(f"Auto-start failed: {result[:200]}")
                self._connected = False
                return False
            self._connected = True
            logger.info("WhatsApp bot auto-started successfully")
            return True
        except Exception as e:
            logger.warning(f"Auto-start exception: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        try:
            from xeno.tools.whatsapp import whatsapp_stop_bot
            await whatsapp_stop_bot()
            self._connected = False
            return True
        except Exception:
            self._connected = False
            return False

    async def handle_event(self, event_type: str, data: dict) -> str:
        if event_type == "incoming_message":
            sender = data.get("from", "unknown")
            message = data.get("message", "")
            self._temporal_kg.add_fact("whatsapp", f"last_message_from_{sender}", message,
                                       source="event", metadata={"sender": sender})
            return f"Received message from {sender}: {message[:100]}"

        elif event_type == "send":
            to = data.get("to", "")
            message = data.get("message", "")
            try:
                from xeno.tools.whatsapp import whatsapp_send
                result = whatsapp_send(to, message)
                self._temporal_kg.add_fact("whatsapp", f"sent_to_{to}", message[:100],
                                           source="mcp_call", metadata={"full_length": len(message)})
                return str(result)
            except Exception as e:
                return f"Error sending: {e}"

        elif event_type == "status":
            return str(await self._mcp_get_status())

        return f"Unknown event type: {event_type}"

    async def run_iteration(self) -> dict:
        if not self._connected:
            await self.connect()
            if not self._connected:
                return {"status": "not_running", "messages": 0}
        try:
            from xeno.tools.whatsapp import whatsapp_status, whatsapp_bot_logs
            status = whatsapp_status()
            if "not started" in str(status).lower() or "has not been started" in str(status).lower():
                self._connected = False
                await self.connect()
                return {"status": "reconnecting", "messages": 0}

            logs = whatsapp_bot_logs(lines=5)
            self._temporal_kg.add_fact("whatsapp", "iteration_check", "ok",
                                       source="iteration", metadata={"logs_preview": str(logs)[:100]})
            return {"status": "ok", "logs": str(logs)[:200]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _cleanup(self):
        await self.disconnect()


def create_whatsapp_agent(duration_hours: float = 0,
                           mode: AgentMode = AgentMode.DUAL) -> WhatsAppAgent:
    """Factory function for WhatsApp agent."""
    config = AgentConfig(
        name="whatsapp",
        provider_type="whatsapp",
        mode=mode,
        duration_hours=duration_hours,
        schedule_interval_seconds=60,
    )
    return WhatsAppAgent(config)
