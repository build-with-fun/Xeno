"""MCP Gateway — unified auth/audit/rate-limit layer for all MCP tool calls.

Every tool call passes through the gateway. The gateway:
1. Checks authorization (caller has permission to use this tool)
2. Rate-limits calls per caller
3. Logs every call to audit trail
4. Injects additional context if configured
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    id: str
    timestamp: float
    caller: str
    server: str
    tool: str
    arguments: dict
    result_preview: str
    duration_ms: float
    approved: bool
    error: str = ""


class MCPGateway:
    """Central gateway for all MCP tool calls."""

    def __init__(self):
        self._audit_log: list[AuditEntry] = []
        self._rate_limits: dict[str, list[float]] = {}
        self._max_calls_per_minute = 60
        self._allowed_callers: set[str] = set()
        self._denied_tools: dict[str, set[str]] = {}  # caller → {tool_names}
        self._hooks: list[Callable] = []
        self._entry_counter = 0

    def allow_caller(self, caller: str):
        self._allowed_callers.add(caller)

    def deny_tool(self, caller: str, tool_name: str):
        self._denied_tools.setdefault(caller, set()).add(tool_name)

    def allow_tool(self, caller: str, tool_name: str):
        self._denied_tools.get(caller, set()).discard(tool_name)

    def register_hook(self, hook: Callable):
        self._hooks.append(hook)

    async def check(self, caller: str, server: str, tool: str, arguments: dict) -> tuple[bool, str]:
        """Check if a tool call is authorized. Returns (allowed, reason)."""

        if caller not in self._allowed_callers:
            return False, f"Caller '{caller}' not authorized"

        denied = self._denied_tools.get(caller, set())
        if tool in denied:
            return False, f"Tool '{tool}' denied for caller '{caller}'"
        if f"{server}.{tool}" in denied:
            return False, f"Tool '{server}.{tool}' denied"

        now = time.time()
        recent = self._rate_limits.get(caller, [])
        recent = [t for t in recent if now - t < 60]
        if len(recent) >= self._max_calls_per_minute:
            return False, f"Rate limit exceeded ({self._max_calls_per_minute}/min)"
        recent.append(now)
        self._rate_limits[caller] = recent

        for hook in self._hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    allowed, reason = await hook(caller, server, tool, arguments)
                else:
                    allowed, reason = hook(caller, server, tool, arguments)
                if not allowed:
                    return False, reason
            except Exception as e:
                logger.warning(f"Gateway hook failed: {e}")

        return True, ""

    async def call(self, caller: str, server: str, tool: str, arguments: dict) -> str:
        """Execute a tool call through the gateway. Returns result string."""
        start = time.time()
        approved = True
        error = ""

        allowed, reason = await self.check(caller, server, tool, arguments)
        if not allowed:
            approved = False
            error = reason
            result = f"Blocked by gateway: {reason}"
        else:
            try:
                from xeno.mcp.adapter import get_server
                srv = get_server(server)
                if not srv:
                    result = f"Server '{server}' not found"
                    error = "server_not_found"
                else:
                    result = await srv.call_tool(tool, arguments)
            except Exception as e:
                result = f"Error: {e}"
                error = str(e)

        duration_ms = (time.time() - start) * 1000
        self._entry_counter += 1
        entry = AuditEntry(
            id=f"audit_{self._entry_counter}",
            timestamp=start,
            caller=caller,
            server=server,
            tool=tool,
            arguments=arguments,
            result_preview=str(result)[:200],
            duration_ms=duration_ms,
            approved=approved,
            error=error,
        )
        self._audit_log.append(entry)

        return result

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        return [{"id": e.id, "caller": e.caller, "server": e.server, "tool": e.tool,
                 "approved": e.approved, "duration_ms": e.duration_ms, "error": e.error}
                for e in self._audit_log[-limit:]]

    def stats(self) -> dict:
        total = len(self._audit_log)
        approved = sum(1 for e in self._audit_log if e.approved)
        blocked = total - approved
        avg_duration = sum(e.duration_ms for e in self._audit_log) / total if total else 0
        return {"total_calls": total, "approved": approved, "blocked": blocked,
                "avg_duration_ms": avg_duration, "callers": len(self._allowed_callers)}


_gateway_instance: MCPGateway | None = None


def get_gateway() -> MCPGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = MCPGateway()
    return _gateway_instance
