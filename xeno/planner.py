"""God-Tier Planning Engine.

Multi-phase, adaptive, parallel-aware planning with contingency support.

Planning Levels:
1. Strategic — high-level goal decomposition (what + why)
2. Tactical — detailed step planning (how)
3. Operational — execution-level actions (do)
4. Contingency — backup plans for when things fail

Features:
- Multi-phase plans with dependencies
- Parallel step execution when independent
- Adaptive re-planning based on results
- Resource and time estimation
- Risk assessment per step
- Checkpoint/savepoint support
- Plan quality scoring
- Historical plan learning (what worked, what didn't)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PlanStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ADAPTED = "adapted"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str
    description: str
    action: str  # What to actually do
    tool_hint: str = ""  # Suggested tool
    depends_on: list[str] = field(default_factory=list)  # Step IDs
    parallel: bool = False  # Can run in parallel with siblings
    estimated_seconds: int = 0
    risk: str = "low"
    status: str = "pending"
    result: str = ""
    error: str = ""
    retries_left: int = 2
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlanPhase:
    """A phase contains multiple steps that must complete in order."""
    id: str
    name: str
    description: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    parallel: bool = False  # Can steps within this phase run in parallel?
    gate_check: str = ""  # Condition to proceed to next phase
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "parallel": self.parallel,
            "gate_check": self.gate_check,
            "status": self.status,
        }


@dataclass
class ContingencyPlan:
    """Backup plan for when a step or phase fails."""
    trigger: str  # What failure triggers this
    fallback_steps: list[PlanStep] = field(default_factory=list)
    max_retries: int = 3
    escalation_prompt: str = ""  # What to tell the user

    def to_dict(self) -> dict:
        return {
            "trigger": self.trigger,
            "fallback_steps": [s.to_dict() for s in self.fallback_steps],
            "max_retries": self.max_retries,
            "escalation_prompt": self.escalation_prompt,
        }


@dataclass
class Plan:
    """A complete plan with phases, steps, and contingencies."""
    id: str
    goal: str
    description: str = ""
    phases: list[PlanPhase] = field(default_factory=list)
    contingencies: list[ContingencyPlan] = field(default_factory=list)
    status: str = "draft"
    priority: int = 50
    estimated_total_seconds: int = 0
    actual_elapsed_seconds: float = 0.0
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result_summary: str = ""
    quality_score: float = 0.0  # 0-100, calculated after completion
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "description": self.description,
            "phases": [p.to_dict() for p in self.phases],
            "contingencies": [c.to_dict() for c in self.contingencies],
            "status": self.status,
            "priority": self.priority,
            "estimated_total_seconds": self.estimated_total_seconds,
            "actual_elapsed_seconds": self.actual_elapsed_seconds,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result_summary": self.result_summary,
            "quality_score": self.quality_score,
            "tags": self.tags,
        }


class PlanningEngine:
    """God-Tier Planning Engine.

    Creates, manages, and executes multi-phase plans with:
    - Strategic goal decomposition
    - Tactical step planning
    - Parallel execution awareness
    - Adaptive re-planning
    - Contingency management
    - Quality scoring
    - Historical learning
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.plans_file = data_dir / "plans.json"
        self.history_file = data_dir / "plan_history.json"
        self._plans: dict[str, Plan] = {}
        self._history: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.plans_file.exists():
            try:
                data = json.loads(self.plans_file.read_text(encoding="utf-8"))
                for pid, pdata in data.items():
                    phases = []
                    for pd in pdata.get("phases", []):
                        steps = [PlanStep(**s) for s in pd.get("steps", [])]
                        phases.append(PlanPhase(
                            id=pd["id"], name=pd["name"],
                            description=pd.get("description", ""),
                            steps=steps, parallel=pd.get("parallel", False),
                            gate_check=pd.get("gate_check", ""),
                            status=pd.get("status", "pending"),
                        ))
                    contingencies = [ContingencyPlan(**c) for c in pdata.get("contingencies", [])]
                    self._plans[pid] = Plan(
                        id=pid, goal=pdata["goal"],
                        description=pdata.get("description", ""),
                        phases=phases, contingencies=contingencies,
                        status=pdata.get("status", "draft"),
                        priority=pdata.get("priority", 50),
                        estimated_total_seconds=pdata.get("estimated_total_seconds", 0),
                        created_at=pdata.get("created_at", ""),
                        tags=pdata.get("tags", []),
                    )
            except Exception as e:
                logger.error(f"Failed to load plans: {e}")

        if self.history_file.exists():
            try:
                self._history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                self._history = []

    def _save(self) -> None:
        data = {}
        for pid, plan in self._plans.items():
            data[pid] = plan.to_dict()
        self.plans_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        self.history_file.write_text(json.dumps(self._history[-500:], indent=2, default=str), encoding="utf-8")

    # =========================================================================
    # PLAN CREATION — Strategic Decomposition
    # =========================================================================

    def create_plan(
        self,
        goal: str,
        description: str = "",
        phases: list[dict[str, Any]] | None = None,
        priority: int = 50,
        tags: list[str] | None = None,
        auto_decompose: bool = True,
    ) -> str:
        """Create a new plan. If auto_decompose=True, phases can be added later."""
        plan_id = str(uuid.uuid4())[:8]
        plan = Plan(
            id=plan_id,
            goal=goal,
            description=description,
            priority=priority,
            tags=tags or [],
        )

        if phases:
            for i, phase_data in enumerate(phases):
                phase = PlanPhase(
                    id=f"phase_{i}",
                    name=phase_data.get("name", f"Phase {i+1}"),
                    description=phase_data.get("description", ""),
                    parallel=phase_data.get("parallel", False),
                    gate_check=phase_data.get("gate_check", ""),
                )
                for j, step_data in enumerate(phase_data.get("steps", [])):
                    step = PlanStep(
                        id=f"step_{i}_{j}",
                        description=step_data.get("description", ""),
                        action=step_data.get("action", ""),
                        tool_hint=step_data.get("tool_hint", ""),
                        depends_on=step_data.get("depends_on", []),
                        parallel=step_data.get("parallel", False),
                        estimated_seconds=step_data.get("estimated_seconds", 30),
                        risk=step_data.get("risk", "low"),
                    )
                    phase.steps.append(step)
                    plan.estimated_total_seconds += step.estimated_seconds
                plan.phases.append(phase)

        plan.status = PlanStatus.READY
        self._plans[plan_id] = plan
        self._save()
        return f"Created plan '{goal}' (id: {plan_id}, {len(plan.phases)} phases, est: {plan.estimated_total_seconds}s)"

    def add_phase(
        self,
        plan_id: str,
        name: str,
        steps: list[dict[str, Any]],
        description: str = "",
        parallel: bool = False,
        gate_check: str = "",
    ) -> str:
        """Add a phase to an existing plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        phase_id = f"phase_{len(plan.phases)}"
        phase = PlanPhase(
            id=phase_id, name=name, description=description,
            parallel=parallel, gate_check=gate_check,
        )

        for j, step_data in enumerate(steps):
            step = PlanStep(
                id=f"step_{len(plan.phases)}_{j}",
                description=step_data.get("description", ""),
                action=step_data.get("action", ""),
                tool_hint=step_data.get("tool_hint", ""),
                depends_on=step_data.get("depends_on", []),
                parallel=step_data.get("parallel", False),
                estimated_seconds=step_data.get("estimated_seconds", 30),
                risk=step_data.get("risk", "low"),
            )
            phase.steps.append(step)
            plan.estimated_total_seconds += step.estimated_seconds

        plan.phases.append(phase)
        self._save()
        return f"Added phase '{name}' to plan (id: {phase_id}, {len(steps)} steps)"

    def add_step(
        self,
        plan_id: str,
        phase_id: str,
        description: str,
        action: str,
        tool_hint: str = "",
        depends_on: list[str] | None = None,
        estimated_seconds: int = 30,
        risk: str = "low",
    ) -> str:
        """Add a step to a specific phase."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        for phase in plan.phases:
            if phase.id == phase_id:
                step_id = f"step_{plan.phases.index(phase)}_{len(phase.steps)}"
                step = PlanStep(
                    id=step_id, description=description, action=action,
                    tool_hint=tool_hint, depends_on=depends_on or [],
                    estimated_seconds=estimated_seconds, risk=risk,
                )
                phase.steps.append(step)
                plan.estimated_total_seconds += estimated_seconds
                self._save()
                return f"Added step '{description}' (id: {step_id})"

        return f"Phase '{phase_id}' not found"

    def add_contingency(
        self,
        plan_id: str,
        trigger: str,
        fallback_steps: list[dict[str, Any]],
        escalation_prompt: str = "",
        max_retries: int = 3,
    ) -> str:
        """Add a contingency plan for failure scenarios."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        steps = []
        for i, sd in enumerate(fallback_steps):
            steps.append(PlanStep(
                id=f"contingency_{len(plan.contingencies)}_{i}",
                description=sd.get("description", ""),
                action=sd.get("action", ""),
                tool_hint=sd.get("tool_hint", ""),
            ))

        contingency = ContingencyPlan(
            trigger=trigger,
            fallback_steps=steps,
            max_retries=max_retries,
            escalation_prompt=escalation_prompt,
        )
        plan.contingencies.append(contingency)
        self._save()
        return f"Added contingency for: {trigger}"

    # =========================================================================
    # PLAN EXECUTION — Step-by-step with parallel awareness
    # =========================================================================

    def start_plan(self, plan_id: str) -> str:
        """Mark a plan as executing."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"
        plan.status = PlanStatus.EXECUTING
        plan.started_at = datetime.now().isoformat()
        self._save()
        return f"Plan '{plan.goal}' started executing"

    def get_next_steps(self, plan_id: str) -> list[PlanStep]:
        """Get steps that are ready to execute (all dependencies met)."""
        plan = self._plans.get(plan_id)
        if not plan:
            return []

        ready = []
        for phase in plan.phases:
            if phase.status == "completed":
                continue
            for step in phase.steps:
                if step.status != StepStatus.PENDING:
                    continue
                # Check all dependencies are completed
                deps_met = all(
                    self._get_step_status(plan, dep_id) == StepStatus.COMPLETED
                    for dep_id in step.depends_on
                )
                if deps_met:
                    step.status = StepStatus.READY
                    ready.append(step)
            # Only process current phase (gated)
            if any(s.status == "ready" for s in phase.steps):
                break
        return ready

    def get_parallel_steps(self, plan_id: str) -> list[list[PlanStep]]:
        """Get groups of steps that can run in parallel."""
        plan = self._plans.get(plan_id)
        if not plan:
            return []

        groups = []
        for phase in plan.phases:
            if phase.parallel:
                ready = [s for s in phase.steps if s.status == StepStatus.READY]
                if ready:
                    groups.append(ready)
            else:
                for step in phase.steps:
                    if step.status == StepStatus.READY:
                        groups.append([step])
        return groups

    def complete_step(self, plan_id: str, step_id: str, result: str = "") -> str:
        """Mark a step as completed."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        step = self._find_step(plan, step_id)
        if not step:
            return f"Step '{step_id}' not found"

        step.status = StepStatus.COMPLETED
        step.result = result

        # Check if phase is complete
        phase = self._find_phase(plan, step_id)
        if phase and all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in phase.steps):
            phase.status = "completed"
            logger.info(f"Phase '{phase.name}' completed")

        # Check if plan is complete
        if all(p.status == "completed" for p in plan.phases):
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.now().isoformat()
            if plan.started_at:
                started = datetime.fromisoformat(plan.started_at)
                plan.actual_elapsed_seconds = (datetime.now() - started).total_seconds()
            plan.quality_score = self._calculate_quality(plan)
            self._record_history(plan)

        self._save()
        return f"Step '{step_id}' completed"

    def fail_step(self, plan_id: str, step_id: str, error: str = "") -> str:
        """Mark a step as failed and trigger contingency if available."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        step = self._find_step(plan, step_id)
        if not step:
            return f"Step '{step_id}' not found"

        step.status = StepStatus.FAILED
        step.error = error

        # Check for contingency
        for contingency in plan.contingencies:
            if contingency.trigger in (step.description, step.action, error):
                if step.retries_left > 0:
                    step.retries_left -= 1
                    step.status = StepStatus.PENDING  # Reset for retry
                    self._save()
                    return (
                        f"Step '{step_id}' failed. Contingency triggered. "
                        f"Retries left: {step.retries_left}. "
                        f"Fallback: {contingency.escalation_prompt}"
                    )

        # No contingency or no retries left
        self._save()
        return f"Step '{step_id}' failed: {error}. No contingency available."

    def pause_plan(self, plan_id: str) -> str:
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"
        plan.status = PlanStatus.PAUSED
        self._save()
        return f"Plan paused"

    def resume_plan(self, plan_id: str) -> str:
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"
        plan.status = PlanStatus.EXECUTING
        self._save()
        return f"Plan resumed"

    def cancel_plan(self, plan_id: str) -> str:
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"
        plan.status = PlanStatus.CANCELLED
        self._record_history(plan)
        self._save()
        return f"Plan cancelled"

    # =========================================================================
    # ADAPTIVE RE-PLANNING
    # =========================================================================

    def adapt_plan(
        self,
        plan_id: str,
        reason: str,
        remove_steps: list[str] | None = None,
        add_phases: list[dict[str, Any]] | None = None,
        modify_step: dict[str, Any] | None = None,
    ) -> str:
        """Adapt a plan based on new information or failures."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        plan.status = PlanStatus.ADAPTED
        changes = []

        if remove_steps:
            for step_id in remove_steps:
                for phase in plan.phases:
                    for step in phase.steps:
                        if step.id == step_id:
                            step.status = StepStatus.SKIPPED
                            changes.append(f"Skipped step: {step.description}")

        if add_phases:
            for phase_data in add_phases:
                self.add_phase(
                    plan_id,
                    phase_data["name"],
                    phase_data.get("steps", []),
                    phase_data.get("description", ""),
                )
                changes.append(f"Added phase: {phase_data['name']}")

        if modify_step:
            step = self._find_step(plan, modify_step.get("id", ""))
            if step:
                if "description" in modify_step:
                    step.description = modify_step["description"]
                if "action" in modify_step:
                    step.action = modify_step["action"]
                changes.append(f"Modified step: {step.id}")

        plan.metadata["adaptations"] = plan.metadata.get("adaptations", [])
        plan.metadata["adaptations"].append({
            "reason": reason,
            "changes": changes,
            "at": datetime.now().isoformat(),
        })

        plan.status = PlanStatus.EXECUTING
        self._save()
        return f"Plan adapted ({len(changes)} changes). Reason: {reason}"

    # =========================================================================
    # PLAN ANALYSIS
    # =========================================================================

    def get_plan_summary(self, plan_id: str) -> str:
        """Get a detailed summary of a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return f"Plan '{plan_id}' not found"

        lines = [
            f"Plan: {plan.goal}",
            f"Status: {plan.status}",
            f"Priority: {plan.priority}",
            f"Estimated: {plan.estimated_total_seconds}s",
            f"Actual: {plan.actual_elapsed_seconds:.0f}s" if plan.actual_elapsed_seconds else "",
            f"Quality: {plan.quality_score:.0f}/100" if plan.quality_score else "",
            f"\nPhases ({len(plan.phases)}):",
        ]

        for phase in plan.phases:
            completed = sum(1 for s in phase.steps if s.status == StepStatus.COMPLETED)
            total = len(phase.steps)
            lines.append(
                f"  [{phase.status.upper()}] {phase.name}: "
                f"{completed}/{total} steps"
            )
            for step in phase.steps:
                icon = {"completed": "✓", "failed": "✗", "executing": "●", "pending": "○", "ready": "→"}.get(step.status, "?")
                lines.append(f"    {icon} {step.description}")
                if step.error:
                    lines.append(f"      Error: {step.error}")

        if plan.contingencies:
            lines.append(f"\nContingencies ({len(plan.contingencies)}):")
            for c in plan.contingencies:
                lines.append(f"  If: {c.trigger} -> {len(c.fallback_steps)} fallback steps")

        return "\n".join(lines)

    def list_plans(self, status: str | None = None) -> list[dict]:
        """List all plans, optionally filtered by status."""
        plans = []
        for pid, plan in self._plans.items():
            if status and plan.status != status:
                continue
            plans.append({
                "id": pid,
                "goal": plan.goal,
                "status": plan.status,
                "priority": plan.priority,
                "phases": len(plan.phases),
                "estimated_seconds": plan.estimated_total_seconds,
                "quality_score": plan.quality_score,
            })
        return plans

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get recent plan history for learning."""
        return self._history[-limit:]

    # =========================================================================
    # QUALITY SCORING & LEARNING
    # =========================================================================

    def _calculate_quality(self, plan: Plan) -> float:
        """Calculate plan quality score (0-100)."""
        score = 50.0  # Base

        # Time efficiency
        if plan.estimated_total_seconds > 0 and plan.actual_elapsed_seconds > 0:
            ratio = plan.estimated_total_seconds / plan.actual_elapsed_seconds
            if ratio >= 0.9:
                score += 15  # On time or faster
            elif ratio >= 0.7:
                score += 10
            elif ratio >= 0.5:
                score += 5
            else:
                score -= 10  # Took much longer than expected

        # Step completion rate
        total_steps = sum(len(p.steps) for p in plan.phases)
        completed_steps = sum(
            1 for p in plan.phases for s in p.steps
            if s.status == StepStatus.COMPLETED
        )
        if total_steps > 0:
            completion_rate = completed_steps / total_steps
            score += completion_rate * 20

        # Contingency usage (good if planned for, bad if many failed)
        contingency_fires = sum(
            1 for p in plan.phases for s in p.steps
            if s.status == StepStatus.FAILED
        )
        if contingency_fires == 0:
            score += 10
        elif contingency_fires <= 2:
            score += 5
        else:
            score -= contingency_fires * 2

        # No failed steps bonus
        failed = sum(1 for p in plan.phases for s in p.steps if s.status == StepStatus.FAILED)
        if failed == 0:
            score += 10

        return max(0.0, min(100.0, score))

    def _record_history(self, plan: Plan) -> None:
        """Record completed plan in history for learning."""
        self._history.append({
            "goal": plan.goal,
            "status": plan.status,
            "quality_score": plan.quality_score,
            "estimated_seconds": plan.estimated_total_seconds,
            "actual_seconds": plan.actual_elapsed_seconds,
            "phases": len(plan.phases),
            "total_steps": sum(len(p.steps) for p in plan.phases),
            "completed_steps": sum(
                1 for p in plan.phases for s in p.steps
                if s.status == StepStatus.COMPLETED
            ),
            "contingencies_used": sum(
                1 for p in plan.phases for s in p.steps
                if s.status == StepStatus.FAILED
            ),
            "adaptations": len(plan.metadata.get("adaptations", [])),
            "completed_at": plan.completed_at or datetime.now().isoformat(),
            "tags": plan.tags,
        })

    def get_learning_insights(self) -> str:
        """Analyze plan history to extract patterns and insights."""
        if not self._history:
            return "No plan history yet."

        total = len(self._history)
        avg_quality = sum(h.get("quality_score", 0) for h in self._history) / total
        success_rate = sum(1 for h in self._history if h.get("status") == "completed") / total
        avg_overrun = 0
        time_plans = [h for h in self._history if h.get("estimated_seconds", 0) > 0 and h.get("actual_seconds", 0) > 0]
        if time_plans:
            overruns = [h["actual_seconds"] / max(h["estimated_seconds"], 1) for h in time_plans]
            avg_overrun = sum(overruns) / len(overruns)

        lines = [
            f"Plan History Insights ({total} plans):",
            f"  Avg Quality: {avg_quality:.0f}/100",
            f"  Success Rate: {success_rate*100:.0f}%",
            f"  Avg Time Ratio: {avg_overrun:.1f}x (1.0 = perfect estimate)",
        ]

        # Tag analysis
        tag_counts: dict[str, int] = {}
        tag_quality: dict[str, list[float]] = {}
        for h in self._history:
            for tag in h.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                tag_quality.setdefault(tag, []).append(h.get("quality_score", 0))
        if tag_counts:
            lines.append("\n  By Tag:")
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:5]:
                avg_q = sum(tag_quality[tag]) / len(tag_quality[tag])
                lines.append(f"    {tag}: {count} plans, avg quality {avg_q:.0f}")

        return "\n".join(lines)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_step_status(self, plan: Plan, step_id: str) -> StepStatus:
        for phase in plan.phases:
            for step in phase.steps:
                if step.id == step_id:
                    return StepStatus(step.status)
        return StepStatus.PENDING

    def _find_step(self, plan: Plan, step_id: str) -> PlanStep | None:
        for phase in plan.phases:
            for step in phase.steps:
                if step.id == step_id:
                    return step
        return None

    def _find_phase(self, plan: Plan, step_id: str) -> PlanPhase | None:
        for phase in plan.phases:
            for step in phase.steps:
                if step.id == step_id:
                    return phase
        return None

    def delete_plan(self, plan_id: str) -> str:
        plan = self._plans.pop(plan_id, None)
        if plan:
            self._save()
            return f"Deleted plan '{plan.goal}'"
        return f"Plan '{plan_id}' not found"

    def get_summary(self) -> str:
        total = len(self._plans)
        active = sum(1 for p in self._plans.values() if p.status in (PlanStatus.EXECUTING, PlanStatus.READY))
        completed = sum(1 for p in self._plans.values() if p.status == PlanStatus.COMPLETED)
        return f"Plans: {total} total, {active} active, {completed} completed"
