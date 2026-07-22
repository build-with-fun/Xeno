"""Memory sleep cycle — consolidation + reflection."""
from __future__ import annotations
import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Optional
logger = logging.getLogger(__name__)

@dataclass
class SleepCycleResult:
    started_at: float; completed_at: float
    consolidated: int=0; reflected: int=0; forgotten: int=0
    reflections: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    def to_dict(self): return asdict(self)

class MemorySleepCycle:
    def __init__(self, data_dir, memory_manager, reconciler=None, llm_reflect=None, batch_size=100):
        self.data_dir = data_dir; self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.data_dir / "sleep_log.jsonl"
        self.memory = memory_manager; self.reconciler = reconciler; self.llm = llm_reflect
        self.batch_size = batch_size
    async def run_light_cycle(self):
        return await self._run_cycle(full=False)
    async def run_full_cycle(self):
        return await self._run_cycle(full=True)
    async def _run_cycle(self, full):
        result = SleepCycleResult(time.time(), 0)
        try:
            result.consolidated = self._consolidate_working()
            if full: result.reflections = await self._reflect(); result.reflected = len(result.reflections)
            result.forgotten = self._forget_weak()
        except Exception as e:
            result.errors.append(str(e))
        result.completed_at = time.time()
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), default=str)+"\n")
        except: pass
        return result
    def _consolidate_working(self):
        am = getattr(self.memory, "advanced", None)
        if not am or not hasattr(am, "working") or not hasattr(am, "episodic"): return 0
        count = 0
        for item in am.working.items:
            if item.strength() > 0.5:
                try:
                    am.episodic.record(item.content, event_type="consolidated", importance=item.importance)
                    count += 1
                except: pass
        return count
    async def _reflect(self):
        if not self.llm or not hasattr(self.memory, "advanced"): return []
        am = self.memory.advanced
        recent = am.episodic.get_recent(limit=50) if hasattr(am.episodic, "get_recent") else []
        if not recent: return []
        prompt = f"Reflect on these experiences, identify 1-3 patterns:\n" + "\n".join(f"- {e.content[:100]}" for e in recent[:20])
        try:
            result = await self.llm(prompt) if callable(self.llm) else ""
            return [result] if result else []
        except: return []
    def _forget_weak(self):
        am = getattr(self.memory, "advanced", None)
        if not am: return 0
        count = 0
        if hasattr(am, "episodic") and hasattr(am.episodic, "episodes"):
            before = len(am.episodic.episodes)
            am.episodic.episodes = [ep for ep in am.episodic.episodes if ep.strength() >= 0.05]
            count += before - len(am.episodic.episodes)
        return count
