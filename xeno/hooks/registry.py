"""Hooks system — PreToolUse/PostToolUse/etc."""
from __future__ import annotations
import asyncio, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Union
logger = logging.getLogger(__name__)

class HookEvent(str, Enum):
    PRE_TOOL_USE="pre_tool_use"; POST_TOOL_USE="post_tool_use"
    PRE_COMPACT="pre_compact"; POST_COMPACT="post_compact"
    SESSION_START="session_start"; SESSION_END="session_end"
    USER_PROMPT_SUBMIT="user_prompt_submit"
    PLAN_APPROVED="plan_approved"; PLAN_COMPLETED="plan_completed"
    ERROR="error"; SUB_AGENT_START="sub_agent_start"; SUB_AGENT_END="sub_agent_end"

class HookAction(str, Enum):
    ALLOW="allow"; BLOCK="block"; MODIFY="modify"; INJECT="inject"; DELAY="delay"

@dataclass
class HookContext:
    event: HookEvent; tool_name: str = ""; tool_args: dict = field(default_factory=dict)
    tool_result: Any = None; user_prompt: str = ""; session_id: str = ""
    timestamp: float = field(default_factory=time.time); metadata: dict = field(default_factory=dict)

@dataclass
class HookDecision:
    action: HookAction = HookAction.ALLOW
    modified_args: Optional[dict] = None; modified_result: Any = None
    inject_message: str = ""; block_reason: str = ""; delay_prompt: str = ""
    metadata: dict = field(default_factory=dict)

HookCallback = Union[Callable[[HookContext], HookDecision], Callable[[HookContext], Awaitable[HookDecision]]]

@dataclass
class HookRegistration:
    id: str; event: HookEvent; callback: HookCallback
    priority: int = 50; name: str = ""; enabled: bool = True
    tool_filter: list[str] = field(default_factory=list)
    fire_count: int = 0; last_fired: float = 0

class HookRegistry:
    def __init__(self):
        self._hooks = {e: [] for e in HookEvent}
    def register(self, event, callback, name="", description="", priority=50, tool_filter=None):
        hid = f"hk_{uuid.uuid4().hex[:8]}"
        reg = HookRegistration(id=hid, event=event, callback=callback, name=name or hid,
                               priority=priority, tool_filter=tool_filter or [])
        self._hooks[event].append(reg)
        self._hooks[event].sort(key=lambda r: r.priority)
        return hid
    async def fire(self, event, ctx: HookContext) -> HookDecision:
        final = HookDecision(action=HookAction.ALLOW)
        inject_messages = []
        for hook in self._hooks[event]:
            if not hook.enabled: continue
            if hook.tool_filter and ctx.tool_name and ctx.tool_name not in hook.tool_filter: continue
            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    decision = await hook.callback(ctx)
                else:
                    decision = hook.callback(ctx)
            except Exception as e:
                logger.error(f"Hook {hook.id} failed: {e}"); continue
            hook.fire_count += 1; hook.last_fired = time.time()
            if decision is None: continue
            if decision.action == HookAction.BLOCK: return decision
            if decision.action == HookAction.MODIFY:
                if decision.modified_args is not None:
                    ctx.tool_args = decision.modified_args; final.modified_args = ctx.tool_args
                if decision.modified_result is not None:
                    ctx.tool_result = decision.modified_result; final.modified_result = ctx.tool_result
            if decision.action == HookAction.INJECT and decision.inject_message:
                inject_messages.append(decision.inject_message)
            if decision.action == HookAction.DELAY: return decision
        if inject_messages:
            final.action = HookAction.INJECT
            final.inject_message = "\n\n".join(inject_messages)
        return final
    def stats(self):
        return {"total_hooks": sum(len(h) for h in self._hooks.values()),
                "by_event": {e.value: len(h) for e,h in self._hooks.items()}}
