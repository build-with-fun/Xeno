"""Plan/Act/Reflect modes."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional
from xeno.plan.dag import PlanManager
logger = logging.getLogger(__name__)

class AgentMode(str, Enum):
    CHAT="chat"; PLAN="plan"; ACT="act"; REFLECT="reflect"

@dataclass
class ModeState:
    current: AgentMode = AgentMode.CHAT
    active_plan_id: str = ""
    auto_progress: bool = False

class ModeController:
    def __init__(self, plan_manager: PlanManager):
        self.plan_manager = plan_manager; self.state = ModeState()
    async def enter_plan_mode(self, goal, description=""):
        self.state.current = AgentMode.PLAN
        plan = self.plan_manager.create_plan(goal=goal, description=description)
        self.state.active_plan_id = plan.id; return plan.id
    async def approve_plan(self):
        if not self.state.active_plan_id: return False
        if self.plan_manager.approve_plan(self.state.active_plan_id):
            self.state.current = AgentMode.ACT; return True
        return False
    async def chat_mode(self):
        self.state.current = AgentMode.CHAT
    def status(self):
        return {"mode": self.state.current.value, "active_plan": self.state.active_plan_id}
