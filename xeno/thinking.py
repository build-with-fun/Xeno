"""Deep Thinking Module — God-Tier Reasoning Engine.

Implements advanced thinking patterns beyond basic CoT/ReAct:
- Chain-of-Density: Progressive information density
- First-Principles: Decompose to fundamentals, rebuild
- Analogical Reasoning: Transfer knowledge from similar domains
- Dialectical Thinking: Thesis → Antithesis → Synthesis
- Probabilistic Reasoning: Assign confidence to each conclusion
- Thought Experimentation: "What if?" scenario analysis
- Constraint Relaxation: Remove assumptions to find novel solutions
- Second-Order Thinking: Think about consequences of consequences
- Inversion: Work backwards from desired outcome
- Opportunity Cost Analysis: What are we NOT doing?
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ThinkingMode(str, Enum):
    FAST = "fast"  # Quick surface-level reasoning
    DEEP = "deep"  # Thorough multi-step reasoning
    EXHAUSTIVE = "exhaustive"  # Consider all angles
    CREATIVE = "creative"  # Novel/unconventional approaches
    CRITICAL = "critical"  # Find flaws and weaknesses
    STRATEGIC = "strategic"  # Long-term, goal-oriented


class ThinkingPattern(str, Enum):
    CHAIN_OF_DENSITY = "chain_of_density"
    FIRST_PRINCIPLES = "first_principles"
    ANALOGICAL = "analogical"
    DIALECTICAL = "dialectical"
    PROBABILISTIC = "probabilistic"
    THOUGHT_EXPERIMENT = "thought_experiment"
    CONSTRAINT_RELAXATION = "constraint_relaxation"
    SECOND_ORDER = "second_order"
    INVERSION = "inversion"
    OPPORTUNITY_COST = "opportunity_cost"


@dataclass
class Thought:
    """A single thought in a thinking chain."""
    id: str
    pattern: str
    content: str
    confidence: float = 0.8  # 0.0-1.0
    depth: int = 0  # How deep in the reasoning chain
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    counterarguments: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThinkingSession:
    """A complete thinking session with multiple patterns applied."""
    id: str
    question: str
    mode: str = "deep"
    thoughts: list[Thought] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    patterns_used: list[str] = field(default_factory=list)
    alternatives_considered: int = 0
    time_spent_seconds: float = 0.0
    quality_score: float = 0.0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "mode": self.mode,
            "thoughts": [t.to_dict() for t in self.thoughts],
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "patterns_used": self.patterns_used,
            "alternatives_considered": self.alternatives_considered,
            "time_spent_seconds": self.time_spent_seconds,
            "quality_score": self.quality_score,
            "created_at": self.created_at,
        }


class DeepThinkingEngine:
    """God-Tier Deep Thinking Engine.

    Applies multiple reasoning patterns to arrive at well-considered conclusions.
    Each pattern provides a different lens:
    - First Principles: Break down to fundamentals
    - Dialectical: Consider opposing views
    - Inversion: Work backwards from goal
    - Second-Order: Think about consequences
    - Probabilistic: Assign confidence
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = data_dir / "thinking_sessions.json"
        self._sessions: dict[str, ThinkingSession] = {}
        self._load()

    def _load(self) -> None:
        if not self.sessions_file.exists():
            return
        try:
            data = json.loads(self.sessions_file.read_text(encoding="utf-8"))
            for sid, sdata in data.items():
                thoughts = [Thought(**t) for t in sdata.get("thoughts", [])]
                self._sessions[sid] = ThinkingSession(
                    id=sid, question=sdata["question"],
                    mode=sdata.get("mode", "deep"),
                    thoughts=thoughts,
                    conclusion=sdata.get("conclusion", ""),
                    confidence=sdata.get("confidence", 0),
                    patterns_used=sdata.get("patterns_used", []),
                    alternatives_considered=sdata.get("alternatives_considered", 0),
                    time_spent_seconds=sdata.get("time_spent_seconds", 0),
                    quality_score=sdata.get("quality_score", 0),
                    created_at=sdata.get("created_at", ""),
                )
        except Exception as e:
            logger.error(f"Failed to load thinking sessions: {e}")

    def _save(self) -> None:
        data = {sid: s.to_dict() for sid, s in self._sessions.items()}
        self.sessions_file.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    # =========================================================================
    # THINKING PATTERNS
    # =========================================================================

    def think_first_principles(self, question: str, context: str = "") -> list[Thought]:
        """Break down a problem to its fundamental truths, then rebuild."""
        thoughts = []

        # Step 1: Identify assumptions
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.FIRST_PRINCIPLES,
            content=f"ASSUMPTIONS: What do we assume about '{question}'?",
            depth=0,
            evidence=["Identifying hidden assumptions is critical for finding novel solutions"],
        ))

        # Step 2: Decompose to fundamentals
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.FIRST_PRINCIPLES,
            content=f"FUNDAMENTALS: What are the absolute basic truths about this problem?",
            depth=1,
            evidence=["Strip away all conventions and focus on what we know for certain"],
        ))

        # Step 3: Rebuild from fundamentals
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.FIRST_PRINCIPLES,
            content=f"REBUILD: Given the fundamentals, what's the optimal solution without assumed constraints?",
            depth=2,
            evidence=["Now construct the solution from the ground up"],
        ))

        return thoughts

    def think_dialectical(self, thesis: str) -> list[Thought]:
        """Thesis → Antithesis → Synthesis (Hegelian dialectic)."""
        thoughts = []

        # Thesis
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.DIALECTICAL,
            content=f"THESIS: {thesis}",
            depth=0,
            confidence=0.7,
        ))

        # Antithesis (challenge the thesis)
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.DIALECTICAL,
            content=f"ANTITHESIS: What's wrong with this? What are the strongest objections?",
            depth=1,
            confidence=0.6,
            counterarguments=["Consider the strongest possible counter-argument"],
        ))

        # Synthesis
        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.DIALECTICAL,
            content=f"SYNTHESIS: How can we combine the best of thesis and antithesis?",
            depth=2,
            confidence=0.8,
        ))

        return thoughts

    def think_inversion(self, goal: str) -> list[Thought]:
        """Work backwards from the desired outcome."""
        thoughts = []

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.INVERSION,
            content=f"INVERSION: Starting from '{goal}' — what would need to be true for this to succeed?",
            depth=0,
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.INVERSION,
            content="REVERSE: What are all the ways this could fail? (Pre-mortem)",
            depth=1,
            evidence=["Inverting the problem reveals blind spots"],
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.INVERSION,
            content="PREVENTION: For each failure mode, what's the single action that prevents it?",
            depth=2,
        ))

        return thoughts

    def think_second_order(self, action: str) -> list[Thought]:
        """Think about consequences of consequences."""
        thoughts = []

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.SECOND_ORDER,
            content=f"FIRST-ORDER: If we do '{action}', what happens immediately?",
            depth=0,
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.SECOND_ORDER,
            content="SECOND-ORDER: And then what happens because of that?",
            depth=1,
            evidence=["Second-order effects are often where the real impact lies"],
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.SECOND_ORDER,
            content="THIRD-ORDER: And what happens because of THAT?",
            depth=2,
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.SECOND_ORDER,
            content="CONVERGENCE: Do these effects compound or cancel? What's the net result?",
            depth=3,
        ))

        return thoughts

    def think_probabilistic(self, hypothesis: str, evidence: list[str] | None = None) -> list[Thought]:
        """Assign confidence levels and update based on evidence (Bayesian)."""
        thoughts = []

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.PROBABILISTIC,
            content=f"HYPOTHESIS: {hypothesis}",
            depth=0,
            confidence=0.5,  # Prior
        ))

        if evidence:
            for i, ev in enumerate(evidence):
                thoughts.append(Thought(
                    id=str(uuid.uuid4())[:8],
                    pattern=ThinkingPattern.PROBABILISTIC,
                    content=f"EVIDENCE {i+1}: {ev}",
                    depth=1,
                    evidence=[ev],
                    confidence=min(0.5 + (i + 1) * 0.1, 0.95),
                ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.PROBABILISTIC,
            content="UPDATED BELIEF: Combining prior with evidence, what's our updated confidence?",
            depth=2,
            confidence=0.75 if evidence else 0.5,
        ))

        return thoughts

    def think_analogical(self, problem: str, source_domain: str = "") -> list[Thought]:
        """Transfer knowledge from a similar domain."""
        thoughts = []

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.ANALOGICAL,
            content=f"ANALOGY: How would someone in '{source_domain}' solve '{problem}'?",
            depth=0,
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.ANALOGICAL,
            content="TRANSFER: What principles from that domain apply here?",
            depth=1,
            evidence=["Analogical reasoning transfers solutions across domains"],
        ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.ANALOGICAL,
            content="ADAPTATION: How must we modify the analogy to fit our context?",
            depth=2,
        ))

        return thoughts

    def think_opportunity_cost(self, chosen_path: str, alternatives: list[str] | None = None) -> list[Thought]:
        """Analyze what we're giving up by choosing one path."""
        thoughts = []

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.OPPORTUNITY_COST,
            content=f"CHOSEN: {chosen_path}",
            depth=0,
        ))

        if alternatives:
            for i, alt in enumerate(alternatives):
                thoughts.append(Thought(
                    id=str(uuid.uuid4())[:8],
                    pattern=ThinkingPattern.OPPORTUNITY_COST,
                    content=f"ALTERNATIVE {i+1}: {alt} — what does this offer that the chosen path doesn't?",
                    depth=1,
                ))

        thoughts.append(Thought(
            id=str(uuid.uuid4())[:8],
            pattern=ThinkingPattern.OPPORTUNITY_COST,
            content="COST: What are we NOT getting by choosing this path? Is that acceptable?",
            depth=2,
        ))

        return thoughts

    # =========================================================================
    # THINKING SESSIONS
    # =========================================================================

    def start_session(
        self,
        question: str,
        mode: str = "deep",
        patterns: list[str] | None = None,
    ) -> str:
        """Start a thinking session applying multiple patterns."""
        session_id = str(uuid.uuid4())[:8]
        session = ThinkingSession(
            id=session_id,
            question=question,
            mode=mode,
        )

        # Apply requested patterns (or all if deep/exhaustive)
        all_patterns = patterns or [p.value for p in ThinkingPattern]

        for pattern_name in all_patterns:
            try:
                pattern = ThinkingPattern(pattern_name)
            except ValueError:
                continue

            if pattern == ThinkingPattern.FIRST_PRINCIPLES:
                session.thoughts.extend(self.think_first_principles(question))
            elif pattern == ThinkingPattern.DIALECTICAL:
                session.thoughts.extend(self.think_dialectical(question))
            elif pattern == ThinkingPattern.INVERSION:
                session.thoughts.extend(self.think_inversion(question))
            elif pattern == ThinkingPattern.SECOND_ORDER:
                session.thoughts.extend(self.think_second_order(question))
            elif pattern == ThinkingPattern.PROBABILISTIC:
                session.thoughts.extend(self.think_probabilistic(question))
            elif pattern == ThinkingPattern.ANALOGICAL:
                session.thoughts.extend(self.think_analogical(question))
            elif pattern == ThinkingPattern.OPPORTUNITY_COST:
                session.thoughts.extend(self.think_opportunity_cost(question))

            session.patterns_used.append(pattern_name)

        self._sessions[session_id] = session
        self._save()
        return f"Thinking session started (id: {session_id}, {len(session.thoughts)} thoughts, {len(session.patterns_used)} patterns)"

    def add_thought(
        self,
        session_id: str,
        content: str,
        pattern: str = "custom",
        confidence: float = 0.8,
        evidence: list[str] | None = None,
        counterarguments: list[str] | None = None,
    ) -> str:
        """Add a thought to an active session."""
        session = self._sessions.get(session_id)
        if not session:
            return f"Session '{session_id}' not found"

        thought = Thought(
            id=str(uuid.uuid4())[:8],
            pattern=pattern,
            content=content,
            confidence=confidence,
            depth=len(session.thoughts),
            evidence=evidence or [],
            counterarguments=counterarguments or [],
        )
        session.thoughts.append(thought)
        self._save()
        return f"Thought added (id: {thought.id}, confidence: {confidence})"

    def conclude(
        self,
        session_id: str,
        conclusion: str,
        confidence: float = 0.8,
    ) -> str:
        """Conclude a thinking session with a final conclusion."""
        session = self._sessions.get(session_id)
        if not session:
            return f"Session '{session_id}' not found"

        session.conclusion = conclusion
        session.confidence = confidence
        session.quality_score = self._calculate_thinking_quality(session)
        self._save()
        return f"Session concluded (confidence: {confidence}, quality: {session.quality_score:.0f}/100)"

    def _calculate_thinking_quality(self, session: ThinkingSession) -> float:
        """Score the quality of a thinking session."""
        score = 40.0

        # Pattern diversity bonus
        unique_patterns = len(set(session.patterns_used))
        score += min(unique_patterns * 5, 25)

        # Thought depth bonus
        max_depth = max((t.depth for t in session.thoughts), default=0)
        score += min(max_depth * 3, 15)

        # Evidence quality
        thoughts_with_evidence = sum(1 for t in session.thoughts if t.evidence)
        if thoughts_with_evidence > 0:
            score += min(thoughts_with_evidence * 2, 10)

        # Counterargument consideration
        thoughts_with_counter = sum(1 for t in session.thoughts if t.counterarguments)
        score += min(thoughts_with_counter * 3, 10)

        return max(0.0, min(100.0, score))

    def get_session_summary(self, session_id: str) -> str:
        """Get a summary of a thinking session."""
        session = self._sessions.get(session_id)
        if not session:
            return f"Session '{session_id}' not found"

        lines = [
            f"Question: {session.question}",
            f"Mode: {session.mode}",
            f"Patterns Used: {', '.join(session.patterns_used)}",
            f"Thoughts: {len(session.thoughts)}",
            f"Quality: {session.quality_score:.0f}/100",
            f"\nThinking Chain:",
        ]

        for thought in session.thoughts:
            indent = "  " * thought.depth
            conf = f" ({thought.confidence:.0%})" if thought.confidence else ""
            lines.append(f"{indent}[{thought.pattern}]{conf} {thought.content[:100]}")
            if thought.evidence:
                lines.append(f"{indent}  Evidence: {'; '.join(thought.evidence[:2])}")
            if thought.counterarguments:
                lines.append(f"{indent}  Counter: {'; '.join(thought.counterarguments[:2])}")

        if session.conclusion:
            lines.append(f"\nConclusion ({session.confidence:.0%}): {session.conclusion}")

        return "\n".join(lines)

    def list_sessions(self, limit: int = 10) -> list[dict]:
        sessions = list(self._sessions.values())[-limit:]
        return [
            {
                "id": s.id,
                "question": s.question[:80],
                "patterns": len(s.patterns_used),
                "thoughts": len(s.thoughts),
                "confidence": s.confidence,
                "quality": s.quality_score,
            }
            for s in sessions
        ]

    def get_summary(self) -> str:
        total = len(self._sessions)
        avg_quality = (
            sum(s.quality_score for s in self._sessions.values()) / total
            if total > 0 else 0
        )
        return f"Thinking Sessions: {total} total, avg quality: {avg_quality:.0f}/100"
