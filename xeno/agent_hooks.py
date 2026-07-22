"""Agent hooks system — before/after tool execution callbacks.

Implements the hook pattern from the deepagents guide:
- before_tool_call: runs before each tool execution, can modify args or block
- after_tool_call: runs after each tool execution, can modify output or log
- on_agent_start / on_agent_end: lifecycle hooks
- on_error: error handling hook
- Hook registry with priority ordering
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """Context passed to hook callbacks."""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    agent_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class HookResult:
    """Result of a hook callback — can modify behavior."""

    def __init__(
        self,
        continue_chain: bool = True,
        modified_args: Optional[dict] = None,
        modified_result: Any = None,
        block: bool = False,
        block_reason: str = "",
    ):
        self.continue_chain = continue_chain
        self.modified_args = modified_args
        self.modified_result = modified_result
        self.block = block
        self.block_reason = block_reason

    @classmethod
    def allow(cls) -> HookResult:
        return cls(continue_chain=True)

    @classmethod
    def block(cls, reason: str = "blocked by hook") -> HookResult:
        return cls(block=True, block_reason=reason)

    @classmethod
    def modify_args(cls, args: dict) -> HookResult:
        return cls(continue_chain=True, modified_args=args)

    @classmethod
    def modify_result(cls, result: Any) -> HookResult:
        return cls(continue_chain=True, modified_result=result)


# Type aliases
HookCallback = Callable[[HookContext], HookResult]
LifecycleCallback = Callable[[dict], None]


@dataclass
class RegisteredHook:
    name: str
    callback: HookCallback
    priority: int = 0  # higher = runs first
    tool_filter: Optional[list[str]] = None  # None = all tools
    enabled: bool = True


class AgentHookManager:
    """Manages before/after hooks for tool execution and agent lifecycle.

    Supports:
    - before_tool_call hooks (can modify args, block execution)
    - after_tool_call hooks (can modify output, log)
    - on_agent_start / on_agent_end lifecycle hooks
    - on_error hooks
    - Priority ordering
    - Tool-specific filtering
    """

    def __init__(self):
        self.before_tool_hooks: list[RegisteredHook] = []
        self.after_tool_hooks: list[RegisteredHook] = []
        self.on_start_hooks: list[Callable[[dict], None]] = []
        self.on_end_hooks: list[Callable[[dict], None]] = []
        self.on_error_hooks: list[Callable[[HookContext], None]] = []
        self._execution_log: list[dict] = []

    def before_tool(
        self, name: str, callback: HookCallback,
        priority: int = 0, tool_filter: Optional[list[str]] = None,
    ) -> None:
        """Register a before-tool hook."""
        hook = RegisteredHook(name=name, callback=callback, priority=priority, tool_filter=tool_filter)
        self.before_tool_hooks.append(hook)
        self.before_tool_hooks.sort(key=lambda h: h.priority, reverse=True)

    def after_tool(
        self, name: str, callback: HookCallback,
        priority: int = 0, tool_filter: Optional[list[str]] = None,
    ) -> None:
        """Register an after-tool hook."""
        hook = RegisteredHook(name=name, callback=callback, priority=priority, tool_filter=tool_filter)
        self.after_tool_hooks.append(hook)
        self.after_tool_hooks.sort(key=lambda h: h.priority, reverse=True)

    def on_start(self, callback: LifecycleCallback) -> None:
        self.on_start_hooks.append(callback)

    def on_end(self, callback: LifecycleCallback) -> None:
        self.on_end_hooks.append(callback)

    def on_error(self, callback: Callable[[HookContext], None]) -> None:
        self.on_error_hooks.append(callback)

    def run_before_tool(self, tool_name: str, arguments: dict[str, Any]) -> HookResult:
        """Run all before-tool hooks. Returns combined result."""
        context = HookContext(tool_name=tool_name, arguments=dict(arguments))
        combined_args = dict(arguments)
        for hook in self.before_tool_hooks:
            if not hook.enabled:
                continue
            if hook.tool_filter and tool_name not in hook.tool_filter:
                continue
            try:
                context.arguments = dict(combined_args)
                result = hook.callback(context)
                if result.block:
                    logger.info(f"Hook '{hook.name}' blocked tool '{tool_name}': {result.block_reason}")
                    self._log("before_block", tool_name, hook.name, result.block_reason)
                    return result
                if result.modified_args:
                    combined_args = result.modified_args
            except Exception as e:
                logger.error(f"Hook '{hook.name}' error: {e}")
        self._log("before", tool_name, "", "")
        return HookResult(continue_chain=True, modified_args=combined_args)

    def run_after_tool(self, tool_name: str, result: Any) -> Any:
        """Run all after-tool hooks. Returns (possibly modified) result."""
        context = HookContext(tool_name=tool_name, result=result)
        current_result = result
        for hook in self.after_tool_hooks:
            if not hook.enabled:
                continue
            if hook.tool_filter and tool_name not in hook.tool_filter:
                continue
            try:
                context.result = current_result
                hook_result = hook.callback(context)
                if hook_result.modified_result is not None:
                    current_result = hook_result.modified_result
            except Exception as e:
                logger.error(f"After-hook '{hook.name}' error: {e}")
        self._log("after", tool_name, "", "")
        return current_result

    def run_agent_start(self, metadata: dict[str, Any]) -> None:
        for cb in self.on_start_hooks:
            try:
                cb(metadata)
            except Exception as e:
                logger.error(f"on_start hook error: {e}")

    def run_agent_end(self, metadata: dict[str, Any]) -> None:
        for cb in self.on_end_hooks:
            try:
                cb(metadata)
            except Exception as e:
                logger.error(f"on_end hook error: {e}")

    def run_on_error(self, context: HookContext) -> None:
        for cb in self.on_error_hooks:
            try:
                cb(context)
            except Exception as e:
                logger.error(f"on_error hook error: {e}")

    def remove_hook(self, name: str) -> int:
        """Remove all hooks with a given name."""
        before = len(self.before_tool_hooks)
        self.before_tool_hooks = [h for h in self.before_tool_hooks if h.name != name]
        self.after_tool_hooks = [h for h in self.after_tool_hooks if h.name != name]
        return before - len(self.before_tool_hooks) + (before - len(self.after_tool_hooks))

    def get_execution_log(self, limit: int = 50) -> list[dict]:
        return self._execution_log[-limit:]

    def _log(self, phase: str, tool: str, hook: str, detail: str) -> None:
        self._execution_log.append({
            "phase": phase, "tool": tool, "hook": hook,
            "detail": detail, "ts": time.time(),
        })
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

    def stats(self) -> dict[str, int]:
        return {
            "before_hooks": len(self.before_tool_hooks),
            "after_hooks": len(self.after_tool_hooks),
            "start_hooks": len(self.on_start_hooks),
            "end_hooks": len(self.on_end_hooks),
            "error_hooks": len(self.on_error_hooks),
            "executions": len(self._execution_log),
        }
