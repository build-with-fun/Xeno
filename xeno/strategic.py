"""Strategic Reasoner — Goal Decomposition, Resource Allocation, Risk Analysis.

High-level strategic thinking for complex multi-day/multi-week tasks:
- Goal decomposition (big goal → sub-goals → tasks)
- Resource allocation (what tools, agents, time needed)
- Risk analysis (what could go wrong, mitigation)
- Progress tracking toward strategic goals
- Milestone planning
- Trade-off analysis
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    id: str
    title: str
    description: str = ""
    priority: str = "medium"  # low, medium, high, critical
    status: str = "active"  # active, completed, abandoned, blocked
    deadline: str | None = None
    sub_goals: list[str] = field(default_factory=list)  # Goal IDs
    tasks: list[str] = field(default_factory=list)  # Task descriptions
    resources_needed: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    progress_percent: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Risk:
    id: str
    description: str
    probability: str = "medium"  # low, medium, high
    impact: str = "medium"  # low, medium, high, critical
    mitigation: str = ""
    status: str = "open"  # open, mitigated, accepted, realized
    triggered_by: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class StrategicReasoner:
    """Strategic reasoning engine for long-term goal management."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.goals_file = data_dir / "strategic_goals.json"
        self._goals: dict[str, Goal] = {}
        self._risks: dict[str, Risk] = {}
        self._load()

    def _load(self) -> None:
        if not self.goals_file.exists():
            return
        try:
            data = json.loads(self.goals_file.read_text(encoding="utf-8"))
            for gid, gdata in data.get("goals", {}).items():
                self._goals[gid] = Goal(**gdata)
            for rid, rdata in data.get("risks", {}).items():
                self._risks[rid] = Risk(**rdata)
        except Exception as e:
            logger.error(f"Failed to load strategic data: {e}")

    def _save(self) -> None:
        data = {
            "goals": {gid: g.to_dict() for gid, g in self._goals.items()},
            "risks": {rid: r.to_dict() for rid, r in self._risks.items()},
        }
        self.goals_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        deadline: str | None = None,
        sub_goals: list[str] | None = None,
        tasks: list[str] | None = None,
        resources_needed: list[str] | None = None,
    ) -> str:
        gid = str(uuid.uuid4())[:8]
        goal = Goal(
            id=gid, title=title, description=description,
            priority=priority, deadline=deadline,
            sub_goals=sub_goals or [], tasks=tasks or [],
            resources_needed=resources_needed or [],
        )
        self._goals[gid] = goal
        self._save()
        return f"Created goal '{title}' (id: {gid})"

    def decompose_goal(self, goal_id: str, sub_goals: list[dict[str, Any]], tasks: list[str] | None = None) -> str:
        """Break a goal into sub-goals and tasks."""
        goal = self._goals.get(goal_id)
        if not goal:
            return f"Goal '{goal_id}' not found"

        for sg in sub_goals:
            sg_id = str(uuid.uuid4())[:8]
            sub = Goal(
                id=sg_id, title=sg["title"],
                description=sg.get("description", ""),
                priority=sg.get("priority", goal.priority),
                tasks=sg.get("tasks", []),
                resources_needed=sg.get("resources_needed", []),
            )
            self._goals[sg_id] = sub
            goal.sub_goals.append(sg_id)

        if tasks:
            goal.tasks.extend(tasks)

        self._save()
        return f"Decomposed into {len(sub_goals)} sub-goals"

    def assess_risks(self, goal_id: str, risks: list[dict[str, str]]) -> str:
        """Identify and assess risks for a goal."""
        goal = self._goals.get(goal_id)
        if not goal:
            return f"Goal '{goal_id}' not found"

        for risk_data in risks:
            rid = str(uuid.uuid4())[:8]
            risk = Risk(
                id=rid, description=risk_data["description"],
                probability=risk_data.get("probability", "medium"),
                impact=risk_data.get("impact", "medium"),
                mitigation=risk_data.get("mitigation", ""),
            )
            self._risks[rid] = risk
            goal.risks.append(risk.description)

        self._save()
        return f"Assessed {len(risks)} risks"

    def update_progress(self, goal_id: str, percent: float, status: str | None = None) -> str:
        goal = self._goals.get(goal_id)
        if not goal:
            return f"Goal '{goal_id}' not found"
        goal.progress_percent = min(100.0, max(0.0, percent))
        if status:
            goal.status = status
        goal.updated_at = datetime.now().isoformat()
        self._save()
        return f"Goal '{goal.title}' progress: {percent:.0f}%"

    def get_goal_summary(self, goal_id: str) -> str:
        goal = self._goals.get(goal_id)
        if not goal:
            return f"Goal '{goal_id}' not found"

        lines = [
            f"Goal: {goal.title} [{goal.priority.upper()}]",
            f"Status: {goal.status}",
            f"Progress: {goal.progress_percent:.0f}%",
            f"Deadline: {goal.deadline or 'none'}",
            f"Description: {goal.description}",
            f"\nTasks ({len(goal.tasks)}):",
        ]
        for t in goal.tasks:
            lines.append(f"  - {t}")
        if goal.sub_goals:
            lines.append(f"\nSub-goals ({len(goal.sub_goals)}):")
            for sgid in goal.sub_goals:
                sg = self._goals.get(sgid)
                if sg:
                    lines.append(f"  [{sg.status}] {sg.title} ({sg.progress_percent:.0f}%)")
        if goal.risks:
            lines.append(f"\nRisks ({len(goal.risks)}):")
            for r in goal.risks:
                lines.append(f"  ⚠ {r}")
        if goal.resources_needed:
            lines.append(f"\nResources: {', '.join(goal.resources_needed)}")
        return "\n".join(lines)

    def list_goals(self, status: str | None = None) -> list[dict]:
        goals = []
        for gid, g in self._goals.items():
            if status and g.status != status:
                continue
            goals.append({
                "id": gid, "title": g.title, "status": g.status,
                "priority": g.priority, "progress": g.progress_percent,
                "deadline": g.deadline,
            })
        return goals

    def delete_goal(self, goal_id: str) -> str:
        goal = self._goals.pop(goal_id, None)
        if goal:
            self._save()
            return f"Deleted goal '{goal.title}'"
        return f"Goal '{goal_id}' not found"

    def get_summary(self) -> str:
        total = len(self._goals)
        active = sum(1 for g in self._goals.values() if g.status == "active")
        completed = sum(1 for g in self._goals.values() if g.status == "completed")
        return f"Strategic Goals: {total} total, {active} active, {completed} completed"
