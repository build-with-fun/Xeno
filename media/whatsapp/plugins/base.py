"""Plugin base classes and hook definitions."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class HookPoint(str, enum.Enum):
    """Points in the message processing pipeline where plugins can hook in."""
    BEFORE_DECISION = "before_decision"    # Before AI safety decision
    AFTER_DECISION = "after_decision"      # After AI safety decision
    BEFORE_REPLY = "before_reply"          # Before sending the reply
    AFTER_SEND = "after_send"              # After a message is sent
    ON_SCHEDULE = "on_schedule"            # Periodic background task


@dataclass
class PluginContext:
    """Context passed to plugins at each hook point."""
    contact_name: str
    messages: list[dict] = field(default_factory=list)  # ProcessedMessage dicts
    decision: Optional[dict] = None  # AI decision (for after_decision)
    reply: Optional[str] = None      # Generated reply (for before_reply)
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # Plugin-specific data


@dataclass
class PluginResult:
    """Result from a plugin execution."""
    # If True, stop processing and skip remaining plugins
    stop_processing: bool = False
    # If True, skip the AI reply entirely (e.g., for spam)
    skip_reply: bool = False
    # Modified messages (for before_decision)
    modified_messages: Optional[list[dict]] = None
    # Modified decision (for after_decision)
    modified_decision: Optional[dict] = None
    # Modified reply (for before_reply)
    modified_reply: Optional[str] = None
    # Additional metadata to pass forward
    metadata: dict = field(default_factory=dict)


class Plugin:
    """Base class for all plugins.

    Subclasses must implement at least one hook method.
    Override `name`, `version`, `description`, and the desired hook methods.
    """

    name: str = "base"
    version: str = "1.0.0"
    description: str = "Base plugin"
    author: str = ""
    # Hooks this plugin registers for (subset of HookPoint values)
    hooks: set[HookPoint] = set()
    # Default config (can be overridden via DB)
    default_config: dict = {}

    def __init__(self, config: dict = None):
        self.config = {**self.default_config, **(config or {})}

    def before_decision(self, ctx: PluginContext) -> PluginResult:
        """Called before the AI safety decision. Can modify messages."""
        return PluginResult()

    def after_decision(self, ctx: PluginContext) -> PluginResult:
        """Called after the AI safety decision. Can override the decision."""
        return PluginResult()

    def before_reply(self, ctx: PluginContext) -> PluginResult:
        """Called before sending the reply. Can modify the reply text."""
        return PluginResult()

    def after_send(self, ctx: PluginContext) -> PluginResult:
        """Called after a message is sent. For logging, analytics, etc."""
        return PluginResult()

    def on_schedule(self, ctx: PluginContext) -> PluginResult:
        """Called periodically for background tasks."""
        return PluginResult()

    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version}>"
