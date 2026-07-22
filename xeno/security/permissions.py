"""Permission Model — 3-tier permission system for tool and MCP access.

Levels:
- SAFE: Read-only, information retrieval tools only
- STANDARD: Most tools (read + write to user-approved locations)
- ELEVATED: System-modifying tools (install, exec, file write outside workspace)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class PermissionLevel(Enum):
    SAFE = 0  # Read-only tools
    STANDARD = 1  # Most tools
    ELEVATED = 2  # System-modifying tools


PERMISSION_NAMES = {
    PermissionLevel.SAFE: "safe",
    PermissionLevel.STANDARD: "standard",
    PermissionLevel.ELEVATED: "elevated",
}


@dataclass
class PermissionRule:
    """A single permission rule."""
    tool_name: str  # Tool name or glob pattern (e.g. "filesystem.*", "shell.*")
    level: PermissionLevel
    allow: bool = True
    reason: str = ""

    def matches(self, tool_name: str) -> bool:
        from fnmatch import fnmatch
        return fnmatch(tool_name, self.tool_name)


@dataclass
class PermissionModel:
    """Permission model for a scope (agent, user, session)."""
    base_level: PermissionLevel = PermissionLevel.SAFE
    rules: list[PermissionRule] = field(default_factory=list)
    allowed_tools: set[str] = field(default_factory=set)
    denied_tools: set[str] = field(default_factory=set)

    def check(self, tool_name: str) -> tuple[bool, str]:
        if tool_name in self.denied_tools:
            return False, f"Tool '{tool_name}' explicitly denied"

        for rule in self.rules:
            if rule.matches(tool_name):
                return (rule.allow, rule.reason) if not rule.allow else (True, "")

        if tool_name in self.allowed_tools:
            return True, ""

        return False, f"Tool '{tool_name}' not in allowed set for level {PERMISSION_NAMES[self.base_level]}"

    def grant(self, tool_name: str):
        self.allowed_tools.add(tool_name)

    def deny(self, tool_name: str):
        self.denied_tools.add(tool_name)

    def to_dict(self) -> dict:
        return {
            "base_level": PERMISSION_NAMES[self.base_level],
            "allowed_tools": sorted(self.allowed_tools),
            "denied_tools": sorted(self.denied_tools),
            "rules": [
                {"tool_name": r.tool_name, "level": PERMISSION_NAMES[r.level],
                 "allow": r.allow, "reason": r.reason}
                for r in self.rules
            ],
        }


DEFAULT_TOOL_PERMISSIONS: dict[str, PermissionLevel] = {
    # SAFE: read-only, informational
    "read": PermissionLevel.SAFE,
    "grep": PermissionLevel.SAFE,
    "glob": PermissionLevel.SAFE,
    "list_directory": PermissionLevel.SAFE,
    "web_search": PermissionLevel.SAFE,
    "web_fetch": PermissionLevel.SAFE,
    "temporal_query": PermissionLevel.SAFE,
    "memory_retrieve": PermissionLevel.SAFE,

    # STANDARD: write, but within workspace
    "write": PermissionLevel.STANDARD,
    "edit": PermissionLevel.STANDARD,
    "bash": PermissionLevel.STANDARD,
    "rename": PermissionLevel.STANDARD,
    "delete_file": PermissionLevel.STANDARD,
    "create_directory": PermissionLevel.STANDARD,
    "create_session": PermissionLevel.STANDARD,
    "add_message": PermissionLevel.STANDARD,
    "memory_store": PermissionLevel.STANDARD,
    "schedule_add": PermissionLevel.STANDARD,

    # ELEVATED: system-level
    "pip_install": PermissionLevel.ELEVATED,
    "npm_install": PermissionLevel.ELEVATED,
    "shell_exec": PermissionLevel.ELEVATED,
    "process_start": PermissionLevel.ELEVATED,
    "write_outside_workspace": PermissionLevel.ELEVATED,
    "edit_system_config": PermissionLevel.ELEVATED,
    "install_package": PermissionLevel.ELEVATED,
}
