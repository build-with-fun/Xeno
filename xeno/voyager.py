"""Voyager-style procedural skill library.

Implements the Voyager (Wang et al., 2023) skill library pattern:
- Skill accumulation: skills are discovered and stored over time
- Skill library: searchable collection of executable code skills
- Automatic curriculum: generate new tasks based on progress
- Skill verification: test skills before adding to library
- Skill composition: combine existing skills into new ones

Reference: "Voyager: An Open-Ended Embodied Agent with LLMs"
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Skill:
    id: str
    name: str
    description: str
    code: str
    language: str = "python"
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    version: int = 1
    prerequisites: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    test_code: str = ""
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "code": self.code, "language": self.language, "category": self.category,
            "tags": self.tags, "usage_count": self.usage_count,
            "success_rate": self.success_rate, "created_at": self.created_at,
            "last_used": self.last_used, "version": self.version,
            "prerequisites": self.prerequisites, "examples": self.examples,
            "test_code": self.test_code, "verified": self.verified,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Skill:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SkillUsage:
    skill_id: str
    timestamp: float
    success: bool
    input_summary: str = ""
    output_summary: str = ""
    error: str = ""
    execution_time_ms: float = 0.0


@dataclass
class CurriculumTask:
    id: str
    description: str
    difficulty: str = "medium"
    status: str = "pending"  # pending, in_progress, completed, failed
    skills_used: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "difficulty": self.difficulty, "status": self.status,
            "skills_used": self.skills_used, "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class VoyagerSkillLibrary:
    """Voyager-style skill library with accumulation, verification, and curriculum.

    Features:
    - Add skills from code blocks or manual creation
    - Search by name, tags, category, or embedding similarity
    - Track usage statistics and success rates
    - Verify skills with test execution
    - Generate curriculum tasks
    - Compose new skills from existing ones
    - Version management
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/skills_library")
        self.skills: dict[str, Skill] = {}
        self.usage_log: list[SkillUsage] = []
        self.curriculum: list[CurriculumTask] = []
        self._load()

    def add_skill(
        self, name: str, description: str, code: str,
        language: str = "python", category: str = "general",
        tags: Optional[list[str]] = None, prerequisites: Optional[list[str]] = None,
        test_code: str = "", verified: bool = False,
    ) -> Skill:
        """Add a new skill to the library."""
        # Check for duplicates
        for s in self.skills.values():
            if s.name.lower() == name.lower():
                s.code = code
                s.description = description
                s.version += 1
                s.verified = verified
                self._save()
                return s

        skill = Skill(
            id=f"vsk_{uuid.uuid4().hex[:8]}",
            name=name, description=description, code=code,
            language=language, category=category, tags=tags or [],
            prerequisites=prerequisites or [], test_code=test_code,
            verified=verified,
        )
        self.skills[skill.id] = skill
        self._save()
        return skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        skill = self.skills.get(skill_id)
        if skill:
            skill.usage_count += 1
            skill.last_used = time.time()
        return skill

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        for s in self.skills.values():
            if s.name.lower() == name.lower():
                s.usage_count += 1
                s.last_used = time.time()
                return s
        return None

    def search_skills(
        self, query: str, category: Optional[str] = None,
        tags: Optional[list[str]] = None, limit: int = 10,
    ) -> list[Skill]:
        """Search skills by query, category, and tags."""
        query_words = set(query.lower().split())
        results = []
        for skill in self.skills.values():
            if category and skill.category != category:
                continue
            if tags and not any(t in skill.tags for t in tags):
                continue
            name_words = set(skill.name.lower().split())
            desc_words = set(skill.description.lower().split())
            tag_words = set(t.lower() for t in skill.tags)
            all_words = name_words | desc_words | tag_words
            overlap = len(query_words & all_words)
            score = overlap * 0.5 + (skill.usage_count * 0.1) + (skill.success_rate * 2)
            if overlap > 0 or not query_words:
                results.append((score, skill))
        results.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in results[:limit]]

    def record_usage(
        self, skill_id: str, success: bool,
        input_summary: str = "", output_summary: str = "",
        error: str = "", execution_time_ms: float = 0.0,
    ) -> None:
        """Record skill usage for statistics."""
        usage = SkillUsage(
            skill_id=skill_id, timestamp=time.time(), success=success,
            input_summary=input_summary, output_summary=output_summary,
            error=error, execution_time_ms=execution_time_ms,
        )
        self.usage_log.append(usage)
        if skill_id in self.skills:
            skill = self.skills[skill_id]
            total = skill.usage_count
            if total > 0:
                old_rate = skill.success_rate
                skill.success_rate = (old_rate * total + (1.0 if success else 0.0)) / (total + 1)
        self._save()

    def verify_skill(self, skill_id: str, sandbox_exec: Optional[Any] = None) -> bool:
        """Verify a skill by running its test code."""
        skill = self.skills.get(skill_id)
        if not skill or not skill.test_code:
            return False
        if sandbox_exec:
            try:
                result = sandbox_exec(skill.test_code)
                skill.verified = True
                self._save()
                return True
            except Exception:
                skill.verified = False
                self._save()
                return False
        # No sandbox available — mark as needing verification
        return False

    def compose_skills(self, skill_ids: list[str], new_name: str, new_description: str) -> Optional[Skill]:
        """Compose a new skill from existing skills."""
        codes = []
        all_tags = set()
        all_prereqs = []
        for sid in skill_ids:
            s = self.skills.get(sid)
            if not s:
                return None
            codes.append(f"# --- {s.name} ---\n{s.code}")
            all_tags.update(s.tags)
            all_prereqs.extend(s.prerequisites)
        combined_code = "\n\n".join(codes)
        return self.add_skill(
            name=new_name, description=new_description, code=combined_code,
            tags=list(all_tags), prerequisites=list(set(all_prereqs)),
        )

    def create_curriculum_task(self, description: str, difficulty: str = "medium") -> CurriculumTask:
        task = CurriculumTask(
            id=f"curr_{uuid.uuid4().hex[:8]}",
            description=description, difficulty=difficulty,
        )
        self.curriculum.append(task)
        self._save()
        return task

    def complete_curriculum_task(self, task_id: str, skills_used: Optional[list[str]] = None) -> Optional[CurriculumTask]:
        for task in self.curriculum:
            if task.id == task_id:
                task.status = "completed"
                task.completed_at = time.time()
                task.skills_used = skills_used or []
                self._save()
                return task
        return None

    def get_pending_curriculum(self) -> list[CurriculumTask]:
        return [t for t in self.curriculum if t.status == "pending"]

    def get_top_skills(self, k: int = 10) -> list[Skill]:
        return sorted(self.skills.values(), key=lambda s: s.usage_count, reverse=True)[:k]

    def get_stats(self) -> dict[str, Any]:
        verified = sum(1 for s in self.skills.values() if s.verified)
        total_usage = sum(s.usage_count for s in self.skills.values())
        avg_success = (
            sum(s.success_rate for s in self.skills.values()) / len(self.skills)
            if self.skills else 0.0
        )
        return {
            "total_skills": len(self.skills),
            "verified": verified,
            "total_usage": total_usage,
            "avg_success_rate": round(avg_success, 3),
            "curriculum_tasks": len(self.curriculum),
            "completed_tasks": len([t for t in self.curriculum if t.status == "completed"]),
        }

    def summary(self) -> str:
        s = self.get_stats()
        return (
            f"Voyager Library: {s['total_skills']} skills ({s['verified']} verified), "
            f"{s['total_usage']} uses, {s['avg_success_rate']:.0%} success rate"
        )

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "skills.json").write_text(
            json.dumps({sid: s.to_dict() for sid, s in self.skills.items()}, indent=2)
        )
        (self.data_dir / "usage.json").write_text(
            json.dumps([
                {"skill": u.skill_id, "ts": u.timestamp, "ok": u.success,
                 "input": u.input_summary, "output": u.output_summary,
                 "err": u.error, "ms": u.execution_time_ms}
                for u in self.usage_log[-1000:]
            ], indent=2)
        )
        (self.data_dir / "curriculum.json").write_text(
            json.dumps([t.to_dict() for t in self.curriculum], indent=2)
        )

    def _load(self) -> None:
        skills_path = self.data_dir / "skills.json"
        if skills_path.exists():
            try:
                data = json.loads(skills_path.read_text())
                self.skills = {k: Skill.from_dict(v) for k, v in data.items()}
            except Exception:
                self.skills = {}
        usage_path = self.data_dir / "usage.json"
        if usage_path.exists():
            try:
                data = json.loads(usage_path.read_text())
                self.usage_log = [
                    SkillUsage(skill_id=d["skill"], timestamp=d["ts"], success=d["ok"],
                               input_summary=d.get("input", ""), output_summary=d.get("output", ""),
                               error=d.get("err", ""), execution_time_ms=d.get("ms", 0))
                    for d in data
                ]
            except Exception:
                self.usage_log = []
        curr_path = self.data_dir / "curriculum.json"
        if curr_path.exists():
            try:
                data = json.loads(curr_path.read_text())
                self.curriculum = [CurriculumTask(**d) for d in data]
            except Exception:
                self.curriculum = []
