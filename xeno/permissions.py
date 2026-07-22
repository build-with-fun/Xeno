"""Permission system for Xeno tools.

Implements fine-grained tool access control with permission levels,
role-based access, and runtime permission management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class ToolPermission:
    tool_name: str
    required_level: PermissionLevel
    description: str = ""
    requires_approval: bool = False
    rate_limit: Optional[int] = None  # max calls per session
    allowed_contexts: list[str] = field(default_factory=list)  # empty = all


@dataclass
class AgentRole:
    name: str
    permissions: dict[str, PermissionLevel] = field(default_factory=dict)
    description: str = ""

    def has_permission(self, tool_name: str, level: PermissionLevel) -> bool:
        tool_level = self.permissions.get(tool_name, PermissionLevel.NONE)
        levels = list(PermissionLevel)
        return levels.index(tool_level) >= levels.index(level)


# Predefined roles
ROLES = {
    "admin": AgentRole(
        name="admin",
        description="Full access to all tools",
        permissions={tool: PermissionLevel.ADMIN for tool in [
            "shell_execute", "shell_run_python", "execute_python",
            "mouse_click", "mouse_move", "type_text", "press_key",
            "take_screenshot", "browser_open", "browser_click",
            "browser_type", "browser_evaluate", "browser_close",
            "memory_store", "memory_retrieve", "memory_search",
            "skill_create", "skill_delete", "self_modify",
            "schedule_create", "schedule_delete",
        ]},
    ),
    "standard": AgentRole(
        name="standard",
        description="Standard user with read/write access",
        permissions={
            "shell_execute": PermissionLevel.EXECUTE,
            "shell_run_python": PermissionLevel.EXECUTE,
            "execute_python": PermissionLevel.EXECUTE,
            "browser_open": PermissionLevel.READ,
            "browser_click": PermissionLevel.WRITE,
            "browser_type": PermissionLevel.WRITE,
            "browser_evaluate": PermissionLevel.READ,
            "memory_store": PermissionLevel.WRITE,
            "memory_retrieve": PermissionLevel.READ,
            "memory_search": PermissionLevel.READ,
            "skill_create": PermissionLevel.WRITE,
            "schedule_create": PermissionLevel.WRITE,
        },
    ),
    "restricted": AgentRole(
        name="restricted",
        description="Read-only with limited write access",
        permissions={
            "memory_store": PermissionLevel.WRITE,
            "memory_retrieve": PermissionLevel.READ,
            "memory_search": PermissionLevel.READ,
            "browser_open": PermissionLevel.READ,
            "take_screenshot": PermissionLevel.READ,
        },
    ),
    "readonly": AgentRole(
        name="readonly",
        description="Read-only access",
        permissions={
            "memory_retrieve": PermissionLevel.READ,
            "memory_search": PermissionLevel.READ,
            "take_screenshot": PermissionLevel.READ,
        },
    ),
}


class PermissionManager:
    """Manages tool permissions and access control."""

    def __init__(self, default_role: str = "standard"):
        self.current_role = ROLES.get(default_role, ROLES["standard"])
        self._custom_permissions: dict[str, ToolPermission] = {}
        self._call_counts: dict[str, int] = {}
        self._session_id: Optional[str] = None

    def set_role(self, role_name: str) -> bool:
        """Set the current agent role."""
        if role_name in ROLES:
            self.current_role = ROLES[role_name]
            self._call_counts.clear()
            return True
        return False

    def get_role(self) -> AgentRole:
        """Get the current role."""
        return self.current_role

    def register_tool(self, permission: ToolPermission) -> None:
        """Register a tool permission definition."""
        self._custom_permissions[permission.tool_name] = permission

    def check_permission(self, tool_name: str, level: PermissionLevel = PermissionLevel.READ) -> bool:
        """Check if the current role has permission for a tool at the given level."""
        return self.current_role.has_permission(tool_name, level)

    def check_rate_limit(self, tool_name: str) -> bool:
        """Check if a tool has exceeded its rate limit."""
        custom = self._custom_permissions.get(tool_name)
        if not custom or not custom.rate_limit:
            return True
        count = self._call_counts.get(tool_name, 0)
        return count < custom.rate_limit

    def record_call(self, tool_name: str) -> None:
        """Record a tool call for rate limiting."""
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1

    def can_execute(self, tool_name: str) -> tuple[bool, str]:
        """Comprehensive check: permission + rate limit. Returns (allowed, reason)."""
        if not self.check_permission(tool_name, PermissionLevel.EXECUTE):
            return False, f"Role '{self.current_role.name}' lacks execute permission for '{tool_name}'"

        if not self.check_rate_limit(tool_name):
            limit = self._custom_permissions.get(tool_name)
            return False, f"Rate limit exceeded for '{tool_name}' (limit: {limit.rate_limit})"

        return True, "OK"

    def get_tool_level(self, tool_name: str) -> PermissionLevel:
        """Get the current permission level for a tool."""
        return self.current_role.permissions.get(tool_name, PermissionLevel.NONE)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all tools with their current permission levels."""
        all_tools = set(self.current_role.permissions.keys())
        all_tools.update(self._custom_permissions.keys())

        return [
            {
                "tool": tool,
                "level": self.current_role.permissions.get(tool, PermissionLevel.NONE).value,
                "custom": tool in self._custom_permissions,
            }
            for tool in sorted(all_tools)
        ]

    def stats(self) -> dict[str, Any]:
        return {
            "role": self.current_role.name,
            "tools": len(self.current_role.permissions),
            "call_counts": dict(self._call_counts),
        }
