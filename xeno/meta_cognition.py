"""Meta-Cognition Module — Think About Thinking.

The agent's ability to monitor, evaluate, and regulate its own reasoning:
- Confidence calibration (are we overconfident?)
- Blind spot detection
- Reasoning quality assessment
- Cognitive bias detection
- Plan self-evaluation
- Thought pattern selection
- Learning from reasoning errors
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
class ReasoningRecord:
    """Record of a reasoning attempt for self-evaluation."""
    id: str
    question: str
    approach: str
    conclusion: str
    confidence_before: float  # How confident before reasoning
    confidence_after: float  # How confident after reasoning
    was_correct: bool | None = None  # Set after verification
    patterns_used: list[str] = field(default_factory=list)
    biases_detected: list[str] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CognitiveBias:
    """A known cognitive bias to watch for."""
    name: str
    description: str
    detection_prompt: str  # Question to ask to detect this bias
    mitigation: str  # How to counteract it
    severity: str = "medium"


class MetaCognition:
    """Meta-Cognitive Engine — thinks about thinking.

    Features:
    - Tracks reasoning quality over time
    - Detects cognitive biases in reasoning
    - Calibrates confidence (are we overconfident?)
    - Identifies blind spots
    - Recommends reasoning patterns
    - Learns from reasoning errors
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.records_file = data_dir / "reasoning_records.json"
        self._records: list[ReasoningRecord] = []
        self._biases = self._init_biases()
        self._load()

    def _load(self) -> None:
        if self.records_file.exists():
            try:
                data = json.loads(self.records_file.read_text(encoding="utf-8"))
                self._records = [ReasoningRecord(**r) for r in data]
            except Exception:
                self._records = []

    def _save(self) -> None:
        data = [r.to_dict() for r in self._records[-500:]]
        self.records_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _init_biases(self) -> list[CognitiveBias]:
        return [
            CognitiveBias(
                name="Confirmation Bias",
                description="Seeking information that confirms existing beliefs",
                detection_prompt="Am I only looking at evidence that supports my conclusion?",
                mitigation="Actively seek disconfirming evidence. Ask: what would prove me wrong?",
                severity="high",
            ),
            CognitiveBias(
                name="Anchoring",
                description="Over-relying on the first piece of information",
                detection_prompt="Am I being influenced by the first number or fact I encountered?",
                mitigation="Consider multiple reference points. Reset your mental anchor.",
                severity="medium",
            ),
            CognitiveBias(
                name="Dunning-Kruger",
                description="Overestimating competence in unfamiliar areas",
                detection_prompt="Do I actually have expertise in this, or am I guessing?",
                mitigation="Be honest about knowledge gaps. Seek expert input.",
                severity="high",
            ),
            CognitiveBias(
                name="Sunk Cost Fallacy",
                description="Continuing because of past investment, not future value",
                detection_prompt="Am I continuing this because it's right, or because I've already invested?",
                mitigation="Evaluate based on future value only. Ignore past costs.",
                severity="high",
            ),
            CognitiveBias(
                name="Availability Heuristic",
                description="Judging likelihood by how easily examples come to mind",
                detection_prompt="Am I judging frequency by how memorable recent examples are?",
                mitigation="Seek base rate data. Don't let vivid examples dominate.",
                severity="medium",
            ),
            CognitiveBias(
                name="Overconfidence",
                description="Being more confident than evidence supports",
                detection_prompt="Is my confidence level justified by the strength of my evidence?",
                mitigation="Apply the 'outside view' — how often are similar predictions correct?",
                severity="high",
            ),
            CognitiveBias(
                name="Bandwagon Effect",
                description="Adopting beliefs because many others hold them",
                detection_prompt="Do I believe this because it's true, or because many others believe it?",
                mitigation="Evaluate the evidence independently of popularity.",
                severity="medium",
            ),
            CognitiveBias(
                name="Hindsight Bias",
                description="Believing an outcome was predictable after it happened",
                detection_prompt="Would I have predicted this BEFORE knowing the outcome?",
                mitigation="Keep predictions and evaluations separate. Record predictions first.",
                severity="low",
            ),
            CognitiveBias(
                name="Narrow Framing",
                description="Considering too few options or perspectives",
                detection_prompt="Am I considering enough alternatives, or just the obvious ones?",
                mitigation="Force yourself to list at least 3 alternatives before deciding.",
                severity="medium",
            ),
            CognitiveBias(
                name="Action Bias",
                description="Feeling the need to act even when waiting is better",
                detection_prompt="Is doing nothing a valid option here?",
                mitigation="Consider: what happens if I do nothing? Sometimes patience is optimal.",
                severity="medium",
            ),
        ]

    # =========================================================================
    # CONFIDENCE CALIBRATION
    # =========================================================================

    def record_reasoning(
        self,
        question: str,
        approach: str,
        conclusion: str,
        confidence_before: float,
        confidence_after: float,
        patterns_used: list[str] | None = None,
    ) -> str:
        """Record a reasoning attempt for later evaluation."""
        record = ReasoningRecord(
            id=str(uuid.uuid4())[:8],
            question=question,
            approach=approach,
            conclusion=conclusion,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            patterns_used=patterns_used or [],
        )
        self._records.append(record)
        self._save()
        return f"Recorded reasoning (id: {record.id})"

    def evaluate_reasoning(self, record_id: str, was_correct: bool) -> str:
        """Evaluate whether a reasoning attempt was correct."""
        for record in self._records:
            if record.id == record_id:
                record.was_correct = was_correct
                record.quality_score = self._calculate_record_quality(record)
                self._save()
                return f"Reasoning evaluated: {'correct' if was_correct else 'incorrect'}"
        return f"Record '{record_id}' not found"

    def get_calibration_report(self) -> str:
        """Analyze if we're well-calibrated (confident when right, uncertain when wrong)."""
        evaluated = [r for r in self._records if r.was_correct is not None]
        if not evaluated:
            return "No evaluated reasoning records yet."

        # Group by confidence bucket
        buckets = {}
        for r in evaluated:
            bucket = round(r.confidence_after * 10) / 10  # Round to nearest 0.1
            if bucket not in buckets:
                buckets[bucket] = {"total": 0, "correct": 0}
            buckets[bucket]["total"] += 1
            if r.was_correct:
                buckets[bucket]["correct"] += 1

        lines = ["Confidence Calibration Report:"]
        for bucket in sorted(buckets.keys()):
            data = buckets[bucket]
            actual_accuracy = data["correct"] / data["total"] if data["total"] > 0 else 0
            gap = bucket - actual_accuracy
            status = "✓" if abs(gap) < 0.1 else "⚠ OVERCONFIDENT" if gap > 0 else "⚠ UNDERCONFIDENT"
            lines.append(
                f"  {bucket:.0%} confidence → {actual_accuracy:.0%} actual accuracy "
                f"({data['total']} samples) {status}"
            )

        # Overall metrics
        total_correct = sum(1 for r in evaluated if r.was_correct)
        overall_accuracy = total_correct / len(evaluated)
        avg_confidence = sum(r.confidence_after for r in evaluated) / len(evaluated)
        calibration_error = abs(avg_confidence - overall_accuracy)

        lines.append(f"\n  Overall: {overall_accuracy:.0%} accuracy, {avg_confidence:.0%} avg confidence")
        lines.append(f"  Calibration Error: {calibration_error:.2%} {'(good)' if calibration_error < 0.1 else '(needs improvement)'}")

        return "\n".join(lines)

    # =========================================================================
    # BIAS DETECTION
    # =========================================================================

    def detect_biases(self, reasoning_text: str) -> list[dict[str, str]]:
        """Check reasoning text for cognitive biases."""
        detected = []
        text_lower = reasoning_text.lower()

        bias_indicators = {
            "Confirmation Bias": ["confirm", "obviously", "clearly", "of course", "everyone knows"],
            "Anchoring": ["first", "initial", "started with", "based on the original"],
            "Dunning-Kruger": ["easy", "simple", "just", "trivial", "obvious solution"],
            "Sunk Cost Fallacy": ["already invested", "already spent", "so far", "at this point"],
            "Availability Heuristic": ["recently", "just saw", "remember when", "that time"],
            "Overconfidence": ["definitely", "certain", "guaranteed", "100%", "no doubt"],
            "Bandwagon Effect": ["everyone", "most people", "popular opinion", "standard practice"],
            "Action Bias": ["need to do something", "can't wait", "must act now", "urgent"],
        }

        for bias in self._biases:
            indicators = bias_indicators.get(bias.name, [])
            for indicator in indicators:
                if indicator in text_lower:
                    detected.append({
                        "bias": bias.name,
                        "description": bias.description,
                        "detection": bias.detection_prompt,
                        "mitigation": bias.mitigation,
                        "indicator": indicator,
                    })
                    break

        return detected

    # =========================================================================
    # BLIND SPOT DETECTION
    # =========================================================================

    def identify_blind_spots(self, reasoning_text: str, question: str) -> list[str]:
        """Identify potential blind spots in reasoning."""
        blind_spots = []
        text_lower = reasoning_text.lower()

        # Check for missing perspectives
        perspectives = ["technical", "business", "user", "security", "performance", "cost", "time", "quality"]
        missing = [p for p in perspectives if p not in text_lower]
        if missing:
            blind_spots.append(f"Missing perspectives: {', '.join(missing[:3])}")

        # Check for lack of evidence
        evidence_words = ["because", "evidence", "data shows", "research indicates", "proven"]
        if not any(w in text_lower for w in evidence_words):
            blind_spots.append("No supporting evidence cited")

        # Check for no alternatives considered
        alt_words = ["alternative", "option", "instead", "could also", "another approach"]
        if not any(w in text_lower for w in alt_words):
            blind_spots.append("No alternative approaches considered")

        # Check for no failure analysis
        failure_words = ["risk", "could fail", "what if", "failure", "problem"]
        if not any(w in text_lower for w in failure_words):
            blind_spots.append("No failure modes analyzed")

        # Check for temporal blind spots
        time_words = ["long term", "future", "downstream", "consequence", "later"]
        if not any(w in text_lower for w in time_words):
            blind_spots.append("No long-term consequences considered")

        return blind_spots

    # =========================================================================
    # PATTERN RECOMMENDATION
    # =========================================================================

    def recommend_patterns(self, question: str) -> list[dict[str, str]]:
        """Recommend thinking patterns based on the question type."""
        recommendations = []
        q_lower = question.lower()

        if any(w in q_lower for w in ["why", "cause", "reason", "because"]):
            recommendations.append({
                "pattern": "first_principles",
                "reason": "Causal question — break down to fundamentals",
            })

        if any(w in q_lower for w in ["should i", "choose", "decide", "option", "better"]):
            recommendations.append({
                "pattern": "opportunity_cost",
                "reason": "Decision question — analyze what you're giving up",
            })
            recommendations.append({
                "pattern": "inversion",
                "reason": "Decision question — work backwards from desired outcome",
            })

        if any(w in q_lower for w in ["risk", "danger", "fail", "wrong", "safe"]):
            recommendations.append({
                "pattern": "second_order",
                "reason": "Risk question — think about consequences of consequences",
            })
            recommendations.append({
                "pattern": "inversion",
                "reason": "Risk question — what would cause failure?",
            })

        if any(w in q_lower for w in ["build", "create", "design", "architect", "plan"]):
            recommendations.append({
                "pattern": "first_principles",
                "reason": "Creative question — decompose and rebuild",
            })
            recommendations.append({
                "pattern": "constraint_relaxation",
                "reason": "Creative question — remove assumed constraints",
            })

        if any(w in q_lower for w in ["believe", "think", "opinion", "agree", "debate"]):
            recommendations.append({
                "pattern": "dialectical",
                "reason": "Opinion question — consider thesis, antithesis, synthesis",
            })
            recommendations.append({
                "pattern": "probabilistic",
                "reason": "Opinion question — assign confidence to beliefs",
            })

        if any(w in q_lower for w in ["similar", "like", "analog", "remind"]):
            recommendations.append({
                "pattern": "analogical",
                "reason": "Similarity question — transfer from known domain",
            })

        if not recommendations:
            recommendations.append({
                "pattern": "first_principles",
                "reason": "Default — always good to start with fundamentals",
            })
            recommendations.append({
                "pattern": "dialectical",
                "reason": "Default — consider opposing views",
            })

        return recommendations

    # =========================================================================
    # LEARNING
    # =========================================================================

    def get_learning_insights(self) -> str:
        """Extract patterns from past reasoning to improve future thinking."""
        if not self._records:
            return "No reasoning records to analyze."

        evaluated = [r for r in self._records if r.was_correct is not None]
        if not evaluated:
            return f"{len(self._records)} records, 0 evaluated."

        correct = [r for r in evaluated if r.was_correct]
        incorrect = [r for r in evaluated if not r.was_correct]

        lines = ["Meta-Cognitive Learning Insights:"]

        if incorrect:
            lines.append(f"\n  Common errors ({len(incorrect)} incorrect):")
            for r in incorrect[:5]:
                lines.append(f"    Q: {r.question[:60]}...")
                lines.append(f"    A: {r.conclusion[:60]}...")
                if r.biases_detected:
                    lines.append(f"    Biases: {', '.join(r.biases_detected)}")
                if r.blind_spots:
                    lines.append(f"    Blind spots: {', '.join(r.blind_spots)}")

        # Pattern effectiveness
        pattern_stats: dict[str, dict] = {}
        for r in evaluated:
            for p in r.patterns_used:
                if p not in pattern_stats:
                    pattern_stats[p] = {"total": 0, "correct": 0}
                pattern_stats[p]["total"] += 1
                if r.was_correct:
                    pattern_stats[p]["correct"] += 1

        if pattern_stats:
            lines.append("\n  Pattern effectiveness:")
            for pattern, stats in sorted(pattern_stats.items(), key=lambda x: -x[1]["correct"] / max(x[1]["total"], 1)):
                effectiveness = stats["correct"] / max(stats["total"], 1)
                lines.append(f"    {pattern}: {effectiveness:.0%} ({stats['correct']}/{stats['total']})")

        return "\n".join(lines)

    def _calculate_record_quality(self, record: ReasoningRecord) -> float:
        score = 50.0
        if record.was_correct:
            score += 20
        if record.confidence_after > 0.5 and record.confidence_after < 0.95:
            score += 10  # Well-calibrated confidence
        if record.patterns_used:
            score += min(len(record.patterns_used) * 3, 15)
        if not record.biases_detected:
            score += 5
        return min(100.0, score)

    def get_summary(self) -> str:
        evaluated = [r for r in self._records if r.was_correct is not None]
        correct = sum(1 for r in evaluated if r.was_correct)
        return (
            f"Meta-Cognition: {len(self._records)} records, "
            f"{len(evaluated)} evaluated, {correct} correct"
        )
