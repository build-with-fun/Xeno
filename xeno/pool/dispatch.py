"""Dispatch Plan — structured task descriptions for the AgentPool.

The Main Agent generates dispatch plans: which agents to call,
with what enhanced prompts, at what priority/scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from xeno.pool.scaling import TaskScale


@dataclass
class AgentDispatch:
    """A single agent dispatch instruction."""
    agent_type: str
    prompt: str
    original_prompt: str = ""
    task_id: str = ""
    priority: int = 0  # higher = more urgent
    scale: TaskScale = field(default_factory=TaskScale)
    mcp_servers: list[str] = field(default_factory=list)
    model_override: str = ""
    system_prompt_override: str = ""

    def __post_init__(self):
        if not self.original_prompt:
            self.original_prompt = self.prompt


@dataclass
class DispatchPlan:
    """Collection of dispatches that form a single logical operation."""
    id: str
    goal: str
    dispatches: list[AgentDispatch]
    pattern: str = "fanout"  # fanout, pipeline, supervisor
    metadata: dict = field(default_factory=dict)

    @property
    def total_agents(self) -> int:
        return len(self.dispatches)


# ── Prompt Enhancement Templates ──────────────────────────────────────────

AGENT_PROMPT_TEMPLATES = {
    "research": (
        "You are an expert research agent. Your task:\n"
        "{prompt}\n\n"
        "WORKFLOW:\n"
        "1. Search broadly first with multiple queries\n"
        "2. Cross-reference information from different sources\n"
        "3. Store key findings in memory\n"
        "4. Write a comprehensive report\n"
        "5. Cite all sources with URLs\n\n"
        "Be thorough and accurate. Never fabricate information."
    ),
    "coder": (
        "You are an expert software engineer. Your task:\n"
        "{prompt}\n\n"
        "WORKFLOW:\n"
        "1. Plan the solution architecture first\n"
        "2. Write clean code with error handling\n"
        "3. Test after every change\n"
        "4. Fix issues as they arise\n"
        "5. Document what you built\n\n"
        "Use type hints, follow language conventions."
    ),
    "browser": (
        "You are a browser automation expert. Your task:\n"
        "{prompt}\n\n"
        "WORKFLOW:\n"
        "1. Open the target URL\n"
        "2. Navigate and interact\n"
        "3. Take screenshots at key points\n"
        "4. Extract and save important information\n"
        "5. Verify results visually\n\n"
        "Handle popups and wait for page loads."
    ),
    "planner": (
        "You are a strategic planner. Your task:\n"
        "{prompt}\n\n"
        "WORKFLOW:\n"
        "1. Understand the goal and constraints\n"
        "2. Break into phases with milestones\n"
        "3. Identify dependencies and risks\n"
        "4. Create actionable task items\n"
        "5. Set timelines\n\n"
        "Be methodical and comprehensive."
    ),
    "analyst": (
        "You are a data analysis expert. Your task:\n"
        "{prompt}\n\n"
        "WORKFLOW:\n"
        "1. Understand what insights are needed\n"
        "2. Process and analyze the data\n"
        "3. Create visualizations\n"
        "4. Write clear findings\n"
        "5. Store results in memory\n\n"
        "Explain methodology clearly."
    ),
    "whatsapp": (
        "You are a WhatsApp messaging assistant. Your task:\n"
        "{prompt}\n\n"
        "Be polite. Confirm before sending important messages."
    ),
    "email": (
        "You are an email assistant. Your task:\n"
        "{prompt}\n\n"
        "Format emails professionally. Be concise."
    ),
}


def enhance_prompt(agent_type: str, prompt: str, context: str = "") -> str:
    """Enhance a raw prompt with agent-type-specific instructions."""
    template = AGENT_PROMPT_TEMPLATES.get(agent_type, "{prompt}")
    enhanced = template.replace("{prompt}", prompt)
    if context:
        enhanced = f"Context from main conversation:\n{context}\n\n{enhanced}"
    return enhanced


def build_dispatch_plan(goal: str, agent_types: list[str],
                        prompts: Optional[list[str]] = None,
                        pattern: str = "fanout",
                        context: str = "") -> DispatchPlan:
    """Build a dispatch plan from a goal and agent types."""
    import uuid
    plan = DispatchPlan(
        id=uuid.uuid4().hex[:8],
        goal=goal,
        pattern=pattern,
        dispatches=[],
    )

    for i, agent_type in enumerate(agent_types):
        prompt = prompts[i] if prompts and i < len(prompts) else goal
        enhanced = enhance_prompt(agent_type, prompt, context)
        plan.dispatches.append(AgentDispatch(
            agent_type=agent_type,
            prompt=enhanced,
            original_prompt=prompt,
            task_id=f"{agent_type}_{plan.id}_{i}",
        ))

    return plan
