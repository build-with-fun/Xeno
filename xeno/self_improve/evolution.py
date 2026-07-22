"""Self-evolution engine — RL-based prompt/behavior refinement from execution history.

Inspired by Hermes Agent's self-evolution via prompt tiers, but generalized:
- Tracks task attempts and their outcomes
- Learns which prompt patterns, tool sequences, and approaches work best
- Automatically refines system prompts and skill descriptions
- Generates new skills from successful patterns
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvolutionEvent:
    id: str
    timestamp: float
    event_type: str  # task_complete, task_fail, tool_success, tool_fail, skill_created
    description: str
    pattern_used: str = ""
    outcome_score: float = 0.0  # 0.0 (worst) - 1.0 (best)
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    error_message: str = ""
    duration_ms: int = 0
    tokens_used: int = 0
    prompt_preview: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvolutionInsight:
    id: str
    created_at: float
    insight_type: str  # prompt_refinement, tool_preference, skill_creation, pattern_discovery
    description: str
    confidence: float  # 0.0 - 1.0
    evidence_count: int
    applied: bool = False
    applied_at: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillProposal:
    id: str
    name: str
    description: str
    procedure: list[str]
    trigger_pattern: str
    evidence_count: int
    avg_success_rate: float
    proposed_at: float = field(default_factory=time.time)
    accepted: bool = False
    created_skill_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class EvolutionEngine:
    """Self-evolution engine that learns from execution history."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[EvolutionEvent] = []
        self._insights: list[EvolutionInsight] = []
        self._proposals: list[SkillProposal] = []
        self._load()

    def _load(self):
        for name, target in [("events.json", self._events), ("insights.json", self._insights),
                              ("proposals.json", self._proposals)]:
            p = self.data_dir / name
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    cls_map = {"events.json": EvolutionEvent, "insights.json": EvolutionInsight,
                               "proposals.json": SkillProposal}
                    target.clear()
                    for item in data:
                        cls = cls_map[name]
                        target.append(cls(**item))
                except Exception as e:
                    logger.warning(f"Failed to load {name}: {e}")

    def _save(self):
        for name, source in [("events.json", self._events), ("insights.json", self._insights),
                              ("proposals.json", self._proposals)]:
            p = self.data_dir / name
            try:
                p.write_text(json.dumps([e.to_dict() for e in source[-1000:]], indent=2, default=str), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to save {name}: {e}")

    def record_task(
        self,
        description: str,
        success: bool,
        pattern_used: str = "",
        error_message: str = "",
        duration_ms: int = 0,
        tokens_used: int = 0,
        tags: list[str] = None,
    ):
        ev = EvolutionEvent(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            event_type="task_complete" if success else "task_fail",
            description=description[:300],
            pattern_used=pattern_used,
            outcome_score=1.0 if success else 0.0,
            error_message=error_message[:500],
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            tags=tags or [],
        )
        self._events.append(ev)
        self._save()
        self._analyze()

    def record_tool_call(
        self,
        tool_name: str,
        args: dict,
        success: bool,
        error: str = "",
        duration_ms: int = 0,
    ):
        ev = EvolutionEvent(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            event_type="tool_success" if success else "tool_fail",
            description=f"Tool: {tool_name}",
            tool_name=tool_name,
            tool_args=args,
            outcome_score=1.0 if success else 0.0,
            error_message=error[:500],
            duration_ms=duration_ms,
        )
        self._events.append(ev)
        self._save()

    def _analyze(self):
        if len(self._events) < 5:
            return

        # Analyze tool success rates
        tool_stats: dict[str, dict] = {}
        for ev in self._events:
            if ev.event_type in ("tool_success", "tool_fail") and ev.tool_name:
                if ev.tool_name not in tool_stats:
                    tool_stats[ev.tool_name] = {"success": 0, "fail": 0, "total": 0, "avg_duration": 0}
                s = tool_stats[ev.tool_name]
                if ev.event_type == "tool_success":
                    s["success"] += 1
                else:
                    s["fail"] += 1
                s["total"] += 1
                s["avg_duration"] = (s["avg_duration"] * (s["total"] - 1) + ev.duration_ms) / s["total"]

        # Detect problematic tools
        for tool_name, stats in tool_stats.items():
            if stats["total"] >= 3 and stats["success"] / stats["total"] < 0.4:
                if not any(i.insight_type == "tool_preference" and tool_name in i.description for i in self._insights):
                    insight = EvolutionInsight(
                        id=f"ins_{uuid.uuid4().hex[:8]}",
                        created_at=time.time(),
                        insight_type="tool_preference",
                        description=f"Tool '{tool_name}' has low success rate ({stats['success']}/{stats['total']}). Consider alternatives.",
                        confidence=1.0 - (stats["success"] / stats["total"]),
                        evidence_count=stats["total"],
                    )
                    self._insights.append(insight)
                    logger.info(f"Evolution insight: {insight.description}")

        # Detect successful patterns for skill creation
        task_patterns: dict[str, list[EvolutionEvent]] = defaultdict(list)
        for ev in self._events:
            if ev.event_type == "task_complete" and ev.pattern_used:
                task_patterns[ev.pattern_used].append(ev)

        for pattern, events_list in task_patterns.items():
            if len(events_list) >= 3 and pattern:
                success_count = sum(1 for e in events_list if e.event_type == "task_complete")
                rate = success_count / len(events_list)
                if rate >= 0.8:
                    topic_tags = []
                    for e in events_list:
                        topic_tags.extend(e.tags)
                    common_tags = [t for t in set(topic_tags) if topic_tags.count(t) >= 2]
                    proposal_exists = any(p.trigger_pattern == pattern for p in self._proposals)
                    if not proposal_exists:
                        prop = SkillProposal(
                            id=f"sp_{uuid.uuid4().hex[:8]}",
                            name=f"auto_{pattern.replace(' ', '_')[:30]}",
                            description=f"Pattern '{pattern}' has {success_count}/{len(events_list)} success rate",
                            procedure=[f"Use pattern: {pattern}"],
                            trigger_pattern=pattern,
                            evidence_count=len(events_list),
                            avg_success_rate=rate,
                        )
                        self._proposals.append(prop)
                        logger.info(f"Evolution proposal: new skill '{prop.name}' ({rate:.0%} success)")

        self._save()

    def get_insights(self, min_confidence: float = 0.0) -> list[EvolutionInsight]:
        return [i for i in self._insights if i.confidence >= min_confidence and not i.applied]

    def get_proposals(self, min_success_rate: float = 0.0) -> list[SkillProposal]:
        return [p for p in self._proposals if p.avg_success_rate >= min_success_rate and not p.accepted]

    def mark_applied(self, insight_id: str, success: bool = True):
        for i in self._insights:
            if i.id == insight_id:
                i.applied = True
                i.applied_at = time.time()
                i.success_rate = 1.0 if success else 0.0
                self._save()
                return True
        return False

    def accept_proposal(self, proposal_id: str, skill_path: str = ""):
        for p in self._proposals:
            if p.id == proposal_id:
                p.accepted = True
                p.created_skill_path = skill_path
                self._save()
                return True
        return False

    def stats(self) -> dict:
        return {
            "total_events": len(self._events),
            "total_insights": len(self._insights),
            "pending_insights": len([i for i in self._insights if not i.applied]),
            "total_proposals": len(self._proposals),
            "accepted_proposals": len([p for p in self._proposals if p.accepted]),
        }
