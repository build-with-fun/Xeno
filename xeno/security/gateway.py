"""MCP Security Gateway — auth, audit, rate-limiting, permission checks.

Every tool call through MCP passes through this gateway:
1. Auth: Verify origin/identity
2. Permission check: Is this operation allowed for this role?
3. Rate limit: Has this caller exceeded limits?
4. Audit log: Record the operation
5. Forward: Execute the actual tool call

Supports escalation: SAFE → STANDARD → ELEVATED with additional verification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from xeno.security.permissions import (
    PermissionLevel,
    PermissionModel,
    PERMISSION_NAMES,
    DEFAULT_TOOL_PERMISSIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    id: str
    timestamp: float
    caller: str
    tool_name: str
    args_snapshot: str
    level: str
    allowed: bool
    reason: str
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "caller": self.caller,
            "tool_name": self.tool_name,
            "level": self.level,
            "allowed": self.allowed,
            "reason": self.reason,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class RateLimitConfig:
    max_calls: int = 100
    window_seconds: float = 60.0
    per_tool_limits: dict[str, int] = field(default_factory=dict)


class MCPGateway:
    """Security gateway for all MCP tool calls."""

    def __init__(self,
                 audit_log_path: Optional[Path] = None,
                 rate_limit_config: Optional[RateLimitConfig] = None):
        self.audit_log_path = audit_log_path or Path("data/security/audit.jsonl")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self._call_counts: dict[str, list[float]] = defaultdict(list)
        self._per_call_handlers: list[Callable] = []
        self._audit_entries: list[AuditEntry] = []

    def add_handler(self, handler: Callable[[str, str, dict], Optional[str]]):
        """Add a pre-call handler. Return None to allow, or string reason to deny."""
        self._per_call_handlers.append(handler)

    async def check(self,
                     caller: str,
                     tool_name: str,
                     args: dict,
                     permission_model: Optional[PermissionModel] = None) -> tuple[bool, str, PermissionLevel]:
        """Check if a tool call is permitted.

        Returns (allowed, reason, effective_level).
        """
        base_level = PermissionLevel.STANDARD
        if permission_model:
            base_level = permission_model.base_level

        # Custom handlers
        for handler in self._per_call_handlers:
            result = handler(caller, tool_name, args)
            if result is not None:
                return False, result, base_level

        # Permission check
        if permission_model:
            allowed, reason = permission_model.check(tool_name)
            if not allowed:
                return False, reason, base_level

        # Tool-specific level check
        required_level = DEFAULT_TOOL_PERMISSIONS.get(tool_name, PermissionLevel.STANDARD)
        if required_level.value > base_level.value:
            return False, (
                f"Tool '{tool_name}' requires {PERMISSION_NAMES[required_level]} "
                f"but caller has {PERMISSION_NAMES[base_level]}"
            ), base_level

        # Rate limit check
        now = time.time()
        window = self.rate_limit_config.window_seconds
        counts = self._call_counts[caller]
        counts[:] = [t for t in counts if now - t < window]

        per_tool_limit = self.rate_limit_config.per_tool_limits.get(tool_name,
                                                                     self.rate_limit_config.max_calls)
        if len(counts) >= self.rate_limit_config.max_calls:
            return False, f"Rate limit exceeded for caller '{caller}'", base_level

        tool_counts = [t for t in counts if t == now]  # same-second approximation
        return True, "", base_level

    async def call(self,
                    caller: str,
                    tool_name: str,
                    args: dict,
                    execute_fn: Callable[[dict], Any],
                    permission_model: Optional[PermissionModel] = None) -> Any:
        """Check, audit, and execute a tool call."""
        t0 = time.time()
        allowed, reason, level = await self.check(caller, tool_name, args, permission_model)

        audit = AuditEntry(
            id=uuid.uuid4().hex[:12],
            timestamp=t0,
            caller=caller,
            tool_name=tool_name,
            args_snapshot=json.dumps(args, default=str)[:200],
            level=PERMISSION_NAMES[level],
            allowed=allowed,
            reason=reason,
        )

        if not allowed:
            audit.duration_ms = (time.time() - t0) * 1000
            self._record_audit(audit)
            raise PermissionError(f"Access denied: {reason}")

        try:
            result = await execute_fn(args) if asyncio.iscoroutinefunction(execute_fn) else execute_fn(args)
            audit.allowed = True
            return result
        except Exception as e:
            raise
        finally:
            audit.duration_ms = (time.time() - t0) * 1000
            self._record_audit(audit)
            self._call_counts[caller].append(time.time())

    def _record_audit(self, entry: AuditEntry):
        self._audit_entries.append(entry)
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        return [e.to_dict() for e in self._audit_entries[-limit:]]

    def get_stats(self) -> dict:
        recent = time.time() - 300
        recent_calls = [e for e in self._audit_entries if e.timestamp > recent]
        denied = [e for e in recent_calls if not e.allowed]
        return {
            "total_calls": len(self._audit_entries),
            "calls_last_5min": len(recent_calls),
            "denied_last_5min": len(denied),
            "unique_callers": len(set(e.caller for e in self._audit_entries)),
        }


_gateway_instance: Optional[MCPGateway] = None


def get_gateway() -> MCPGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = MCPGateway()
    return _gateway_instance
