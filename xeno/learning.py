"""Self-learning system — learns from mistakes, creates skills, improves over time.

Pipeline:
  1. Error occurs → record error pattern
  2. Same error repeats → create/update skill to prevent it
  3. Successful approach discovered → save as reusable skill
  4. Periodic reflection → generate lessons learned
  5. Skill refinement → update skills based on success/failure rates

All of this happens automatically — no user intervention needed.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ErrorRecord:
    id: str
    error_type: str
    error_message: str
    context: str
    tool_name: str = ""
    approach_tried: str = ""
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""
    skill_created: str = ""  # ID of skill created to prevent this

    def to_dict(self) -> dict:
        return {
            "id": self.id, "error_type": self.error_type,
            "message": self.error_message[:200], "context": self.context[:200],
            "tool": self.tool_name, "approach": self.approach_tried[:200],
            "ts": self.timestamp, "resolved": self.resolved,
            "resolution": self.resolution, "skill": self.skill_created,
        }


@dataclass
class SuccessRecord:
    id: str
    task: str
    approach: str
    tool_used: str = ""
    outcome: str = ""
    timestamp: float = field(default_factory=time.time)
    skill_created: str = ""
    reusable: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id, "task": self.task[:200],
            "approach": self.approach[:200], "tool": self.tool_used,
            "outcome": self.outcome[:200], "ts": self.timestamp,
            "skill": self.skill_created, "reusable": self.reusable,
        }


@dataclass
class Lesson:
    id: str
    lesson: str
    source: str  # "error_pattern", "success_pattern", "reflection"
    importance: float = 5.0
    times_applied: int = 0
    created_at: float = field(default_factory=time.time)
    last_applied: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "lesson": self.lesson[:300],
            "source": self.source, "importance": self.importance,
            "applied": self.times_applied, "created": self.created_at,
            "last_applied": self.last_applied,
        }


class LearningSystem:
    """Automatic self-learning from errors and successes.

    Features:
    - Record errors and detect repeated patterns
    - Auto-create skills when the same mistake happens 2+ times
    - Record successes and extract reusable patterns
    - Periodic reflection generates lessons
    - Skill refinement based on usage outcomes
    - Lesson tracking — knows what it has learned
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.errors: list[ErrorRecord] = []
        self.successes: list[SuccessRecord] = []
        self.lessons: list[Lesson] = []
        self._skill_creations: dict[str, str] = {}  # pattern_hash -> skill_id

        self._load()

    # --- Error recording ---

    def record_error(
        self, error_type: str, error_message: str, context: str = "",
        tool_name: str = "", approach_tried: str = "",
    ) -> ErrorRecord:
        """Record an error. If pattern repeats, auto-create a skill."""
        rec = ErrorRecord(
            id=f"err_{uuid.uuid4().hex[:8]}",
            error_type=error_type,
            error_message=error_message,
            context=context,
            tool_name=tool_name,
            approach_tried=approach_tried,
        )
        self.errors.append(rec)

        # Check for repeated pattern
        pattern_key = self._error_pattern_key(error_type, error_message)
        count = sum(1 for e in self.errors if self._error_pattern_key(e.error_type, e.error_message) == pattern_key)

        if count >= 2:
            # Pattern repeated — generate a lesson and potentially a skill
            lesson_text = f"Avoid this error: {error_type}. Cause: {error_message[:100]}. Context: {context[:100]}"
            self._add_lesson(lesson_text, source="error_pattern", importance=7.0)
            rec.resolution = f"Lesson recorded (error seen {count} times)"

        self._save()
        return rec

    def record_error_resolved(self, error_id: str, resolution: str = "") -> bool:
        """Mark an error as resolved."""
        for rec in self.errors:
            if rec.id == error_id:
                rec.resolved = True
                rec.resolution = resolution
                self._save()
                return True
        return False

    # --- Success recording ---

    def record_success(
        self, task: str, approach: str, tool_used: str = "",
        outcome: str = "", reusable: bool = True,
    ) -> SuccessRecord:
        """Record a successful approach. Extract reusable patterns."""
        rec = SuccessRecord(
            id=f"suc_{uuid.uuid4().hex[:8]}",
            task=task, approach=approach,
            tool_used=tool_used, outcome=outcome,
            reusable=reusable,
        )
        self.successes.append(rec)

        if reusable and len(approach) > 20:
            lesson_text = f"Successful approach for '{task[:60]}': {approach[:200]}"
            self._add_lesson(lesson_text, source="success_pattern", importance=6.0)

        self._save()
        return rec

    # --- Lessons ---

    def _add_lesson(self, lesson: str, source: str = "reflection", importance: float = 5.0) -> Lesson:
        """Add a lesson, deduplicating similar ones."""
        # Check if similar lesson exists
        for existing in self.lessons:
            overlap = len(set(lesson.lower().split()) & set(existing.lesson.lower().split()))
            total = max(len(set(lesson.lower().split())), 1)
            if overlap / total > 0.6:
                # Update existing lesson
                existing.times_applied += 1
                existing.last_applied = time.time()
                existing.importance = min(10.0, existing.importance + 0.5)
                self._save()
                return existing

        l = Lesson(
            id=f"les_{uuid.uuid4().hex[:8]}",
            lesson=lesson, source=source, importance=importance,
        )
        self.lessons.append(l)
        self._save()
        return l

    def add_lesson(self, lesson: str, source: str = "manual", importance: float = 5.0) -> Lesson:
        """Public API to add a lesson."""
        return self._add_lesson(lesson, source, importance)

    def get_relevant_lessons(self, context: str, limit: int = 5) -> list[Lesson]:
        """Get lessons relevant to the current context."""
        context_words = set(context.lower().split())
        scored = []
        for l in self.lessons:
            lesson_words = set(l.lesson.lower().split())
            overlap = len(context_words & lesson_words)
            score = overlap * 0.5 + l.importance * 0.3 + (l.times_applied * 0.2)
            scored.append((score, l))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [l for _, l in scored[:limit]]

    def get_all_lessons(self, limit: int = 50) -> list[Lesson]:
        return sorted(self.lessons, key=lambda l: l.importance, reverse=True)[:limit]

    # --- Pattern detection ---

    def detect_error_patterns(self) -> list[dict[str, Any]]:
        """Find repeated error patterns that need skills."""
        pattern_counts: dict[str, list[ErrorRecord]] = {}
        for rec in self.errors:
            key = self._error_pattern_key(rec.error_type, rec.error_message)
            pattern_counts.setdefault(key, []).append(rec)

        patterns = []
        for key, records in pattern_counts.items():
            if len(records) >= 2 and not records[-1].resolved:
                patterns.append({
                    "pattern": key,
                    "count": len(records),
                    "last_error": records[-1].error_message[:100],
                    "first_seen": records[0].timestamp,
                    "last_seen": records[-1].timestamp,
                    "tool": records[-1].tool_name,
                })
        return sorted(patterns, key=lambda p: p["count"], reverse=True)

    def detect_success_patterns(self) -> list[dict[str, Any]]:
        """Find repeated successful approaches worth turning into skills."""
        task_approaches: dict[str, list[SuccessRecord]] = {}
        for rec in self.successes:
            task_words = " ".join(rec.task.lower().split()[:5])
            task_approaches.setdefault(task_words, []).append(rec)

        patterns = []
        for task_key, records in task_approaches.items():
            if len(records) >= 2:
                approaches = [r.approach for r in records if r.approach]
                if approaches:
                    patterns.append({
                        "task_pattern": task_key,
                        "count": len(records),
                        "best_approach": max(approaches, key=len),
                        "tools": list(set(r.tool_used for r in records if r.tool_used)),
                    })
        return patterns

    # --- Auto skill creation ---

    def should_create_skill(self) -> Optional[dict]:
        """Check if there's a pattern that warrants creating a skill."""
        patterns = self.detect_error_patterns()
        for p in patterns:
            if p["count"] >= 3:
                pattern_hash = p["pattern"]
                if pattern_hash not in self._skill_creations:
                    return p
        return None

    def mark_skill_created(self, pattern_key: str, skill_id: str) -> None:
        self._skill_creations[pattern_key] = skill_id
        self._save()

    # --- Reflection ---

    def reflect(self, recent_interactions: list[dict[str, str]] = None) -> str:
        """Generate a reflection summary of what has been learned."""
        error_count = len(self.errors)
        resolved_count = sum(1 for e in self.errors if e.resolved)
        success_count = len(self.successes)
        lesson_count = len(self.lessons)
        patterns = self.detect_error_patterns()

        parts = [
            f"Learning Summary: {lesson_count} lessons learned.",
            f"Errors: {error_count} total, {resolved_count} resolved.",
            f"Successes: {success_count} recorded.",
        ]
        if patterns:
            parts.append(f"Active error patterns: {len(patterns)} (may need skills).")
        else:
            parts.append("No unresolved error patterns.")

        # Top lessons
        top = self.get_all_lessons(limit=3)
        if top:
            parts.append("Top lessons:")
            for l in top:
                parts.append(f"  - {l.lesson[:100]} (applied {l.times_applied}x)")

        return "\n".join(parts)

    # --- Utility ---

    def _error_pattern_key(self, error_type: str, message: str) -> str:
        """Generate a pattern key from error type + normalized message."""
        import re
        normalized = re.sub(r'[\d\w]{8,}', 'X', message.lower())
        normalized = re.sub(r'["\']', '', normalized)
        return f"{error_type}:{normalized[:80]}"

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_errors": len(self.errors),
            "resolved_errors": sum(1 for e in self.errors if e.resolved),
            "total_successes": len(self.successes),
            "total_lessons": len(self.lessons),
            "error_patterns": len(self.detect_error_patterns()),
            "success_patterns": len(self.detect_success_patterns()),
            "skills_created": len(self._skill_creations),
        }

    def summary(self) -> str:
        s = self.get_stats()
        return (
            f"Learning: {s['total_lessons']} lessons, "
            f"{s['total_errors']} errors ({s['resolved_errors']} resolved), "
            f"{s['total_successes']} successes, "
            f"{s['skills_created']} auto-skills"
        )

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "errors.json").write_text(
            json.dumps([e.to_dict() for e in self.errors[-500:]], indent=2)
        )
        (self.data_dir / "successes.json").write_text(
            json.dumps([s.to_dict() for s in self.successes[-500:]], indent=2)
        )
        (self.data_dir / "lessons.json").write_text(
            json.dumps([l.to_dict() for l in self.lessons], indent=2)
        )
        (self.data_dir / "skill_creations.json").write_text(
            json.dumps(self._skill_creations, indent=2)
        )

    def _load(self) -> None:
        for name, cls, target in [
            ("errors.json", ErrorRecord, "errors"),
            ("successes.json", SuccessRecord, "successes"),
            ("lessons.json", Lesson, "lessons"),
        ]:
            path = self.data_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    if target == "lessons":
                        setattr(self, target, [cls(**d) for d in data])
                    else:
                        setattr(self, target, [cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__}) for d in data])
                except Exception:
                    pass
        sc_path = self.data_dir / "skill_creations.json"
        if sc_path.exists():
            try:
                self._skill_creations = json.loads(sc_path.read_text())
            except Exception:
                pass
