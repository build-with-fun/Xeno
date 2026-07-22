"""Self-improvement engine — skill mining + A/B testing + evals."""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class SkillSource(str, Enum):
    MANUAL = "manual"
    AUTO_MINED = "auto_mined"
    ERROR_PREVENTION = "error_prevention"
    AB_TEST_WINNER = "ab_test_winner"
    IMPORTED = "imported"


@dataclass
class SkillTrace:
    id: str
    task_description: str
    steps: list[dict] = field(default_factory=list)
    final_success: bool = False
    duration_seconds: float = 0
    tokens_used: int = 0
    pattern_used: str = ""
    user_satisfaction: float = 0.5
    tags: list[str] = field(default_factory=list)
    captured_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class MinedSkill:
    id: str
    name: str
    description: str
    trigger_pattern: str
    procedure: list[dict]
    source: SkillSource = SkillSource.AUTO_MINED
    source_traces: list[str] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    last_used: float = 0
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.5


class SkillMiner:
    """Mines execution traces for reusable skills."""

    def __init__(
        self,
        skills_dir: Path,
        llm_extractor: Optional[Callable[[str], Awaitable[str]]] = None,
        min_traces_for_pattern: int = 2,
    ):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_extractor
        self.min_traces = min_traces_for_pattern
        self._traces: list[SkillTrace] = []
        self._mined_skills: dict[str, MinedSkill] = {}

    def capture_trace(self, trace: SkillTrace) -> None:
        self._traces.append(trace)
        if len(self._traces) > 1000:
            self._traces = self._traces[-1000:]

    async def mine_skills(self, max_skills: int = 5) -> list[MinedSkill]:
        # Simple heuristic-based mining (LLM-enhanced version in production)
        new_skills: list[MinedSkill] = []
        # Group by task type
        groups: dict[str, list[SkillTrace]] = {}
        for trace in self._traces:
            keywords = " ".join(sorted(trace.task_description.lower().split()[:3]))
            if keywords:
                groups.setdefault(keywords, []).append(trace)
        for task_pattern, traces in groups.items():
            if len(traces) < self.min_traces:
                continue
            successful = [t for t in traces if t.final_success]
            if len(successful) < self.min_traces:
                continue
            skill = MinedSkill(
                id=f"skill_{uuid.uuid4().hex[:8]}",
                name=f"auto:{task_pattern[:50]}",
                description=f"Auto-mined skill for: {task_pattern}",
                trigger_pattern=task_pattern,
                procedure=[{"action": "use tools"}],
                source=SkillSource.AUTO_MINED,
                source_traces=[t.id for t in successful],
                confidence=0.6,
            )
            self._mined_skills[skill.id] = skill
            new_skills.append(skill)
            if len(new_skills) >= max_skills:
                break
        return new_skills

    def list_skills(self) -> list[dict]:
        return [
            {
                "id": s.id, "name": s.name, "description": s.description,
                "confidence": s.confidence, "success_count": s.success_count,
            }
            for s in self._mined_skills.values()
        ]

    def find_relevant(self, task_description: str) -> list[MinedSkill]:
        keywords = set(task_description.lower().split())
        scored = []
        for skill in self._mined_skills.values():
            trigger_words = set(skill.trigger_pattern.lower().split())
            overlap = len(keywords & trigger_words)
            if overlap > 0:
                scored.append((overlap * skill.confidence, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:5]]


class ErrorPipeline:
    """Captures failed traces and creates error-prevention skills."""

    def __init__(self, skill_miner: SkillMiner):
        self.miner = skill_miner
        self._error_patterns: dict[str, list[dict]] = {}

    def record_error(self, tool: str, args: dict, error: str, context: dict) -> None:
        key = f"{tool}:{error[:50]}"
        self._error_patterns.setdefault(key, []).append({
            "args": args, "error": error, "context": context, "timestamp": time.time(),
        })
        if len(self._error_patterns[key]) > 100:
            self._error_patterns[key] = self._error_patterns[key][-100:]

    async def generate_prevention_skills(self, threshold: int = 3) -> list[MinedSkill]:
        new_skills: list[MinedSkill] = []
        for pattern, errors in self._error_patterns.items():
            if len(errors) < threshold:
                continue
            tool, error_msg = pattern.split(":", 1)
            skill = MinedSkill(
                id=f"err_skill_{uuid.uuid4().hex[:8]}",
                name=f"avoid:{tool}_error",
                description=f"Avoid common error in {tool}: {error_msg[:80]}",
                trigger_pattern=f"tool={tool}",
                procedure=[
                    {"action": f"Before calling {tool}, validate inputs"},
                    {"action": f"Common error: {error_msg}"},
                    {"action": "Prevention: check args match expected schema"},
                ],
                source=SkillSource.ERROR_PREVENTION,
                confidence=0.6,
                tags=["error_prevention", tool],
            )
            self.miner._mined_skills[skill.id] = skill
            new_skills.append(skill)
        return new_skills


class ABTestRunner:
    """A/B test reasoning patterns on similar tasks."""

    def __init__(self, results_file: Optional[Path] = None):
        self.results_file = results_file
        self._results: dict[str, list[dict]] = {}
        if results_file and results_file.exists():
            self._load()

    def record_result(
        self,
        task_class: str,
        pattern: str,
        success: bool,
        tokens: int = 0,
        duration: float = 0.0,
    ) -> None:
        self._results.setdefault(task_class, []).append({
            "pattern": pattern, "success": success, "tokens": tokens,
            "duration": duration, "timestamp": time.time(),
        })
        self._save()

    def recommend_pattern(self, task_class: str) -> Optional[str]:
        results = self._results.get(task_class, [])
        if len(results) < 2:
            return None
        by_pattern: dict[str, list[dict]] = {}
        for r in results:
            by_pattern.setdefault(r["pattern"], []).append(r)
        best_pattern = None
        best_score = -1
        for pattern, prs in by_pattern.items():
            if len(prs) < 2:
                continue
            success_rate = sum(1 for r in prs if r["success"]) / len(prs)
            avg_tokens = sum(r["tokens"] for r in prs) / len(prs)
            score = success_rate / max(1, avg_tokens / 1000)
            if score > best_score:
                best_score = score
                best_pattern = pattern
        return best_pattern

    def stats(self) -> dict:
        return {
            "task_classes": len(self._results),
            "total_results": sum(len(rs) for rs in self._results.values()),
        }

    def _save(self) -> None:
        if not self.results_file:
            return
        try:
            self.results_file.parent.mkdir(parents=True, exist_ok=True)
            self.results_file.write_text(
                json.dumps(self._results, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"ABTest save failed: {e}")

    def _load(self) -> None:
        try:
            self._results = json.loads(self.results_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"ABTest load failed: {e}")


class EvalSuite:
    """Run a suite of eval tasks before/after self-modifications."""

    def __init__(self, evals_file: Optional[Path] = None):
        self.evals_file = evals_file
        self._evals: list[dict] = []
        self._results: list[dict] = []
        if evals_file and evals_file.exists():
            self._load()

    def add_eval(
        self,
        name: str,
        description: str,
        expected_output: str = "",
        max_tokens: int = 2000,
        max_seconds: int = 30,
        scoring: str = "contains",
    ) -> None:
        self._evals.append({
            "name": name, "description": description,
            "expected_output": expected_output, "max_tokens": max_tokens,
            "max_seconds": max_seconds, "scoring": scoring,
        })
        self._save()

    async def run(self, agent_runner: Callable[[str], Awaitable[str]]) -> dict:
        import asyncio
        results = []
        for ev in self._evals:
            start = time.time()
            try:
                output = await asyncio.wait_for(
                    agent_runner(ev["description"]),
                    timeout=ev["max_seconds"],
                )
                success = self._score(output, ev)
                results.append({
                    "name": ev["name"], "success": success,
                    "output": output[:300], "duration": time.time() - start,
                })
            except Exception as e:
                results.append({
                    "name": ev["name"], "success": False,
                    "error": str(e), "duration": time.time() - start,
                })
        self._results.append({"timestamp": time.time(), "results": results})
        self._save()
        return {
            "total": len(results),
            "passed": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
        }

    def _score(self, output: str, eval_spec: dict) -> bool:
        expected = eval_spec["expected_output"]
        scoring = eval_spec["scoring"]
        if scoring == "contains":
            return expected.lower() in output.lower() if expected else True
        elif scoring == "exact":
            return output.strip() == expected.strip()
        elif scoring == "regex":
            return bool(re.search(expected, output))
        return True

    def _save(self) -> None:
        if not self.evals_file:
            return
        try:
            self.evals_file.parent.mkdir(parents=True, exist_ok=True)
            self.evals_file.write_text(
                json.dumps({"evals": self._evals, "results": self._results}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"EvalSuite save failed: {e}")

    def _load(self) -> None:
        try:
            data = json.loads(self.evals_file.read_text(encoding="utf-8"))
            self._evals = data.get("evals", [])
            self._results = data.get("results", [])
        except Exception as e:
            logger.warning(f"EvalSuite load failed: {e}")
