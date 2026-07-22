"""Context-isolated sub-agents."""
from __future__ import annotations
import asyncio, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    QUEUED="queued"; RUNNING="running"; COMPLETED="completed"
    FAILED="failed"; CANCELLED="cancelled"; TIMEOUT="timeout"

@dataclass
class TaskContext:
    task_id: str; description: str; parent_id: str = "main"
    capability_slice: list[str] = field(default_factory=list)
    memory_slice: dict = field(default_factory=dict)
    file_scope: list[str] = field(default_factory=list)
    budget_tokens: int = 8000; budget_seconds: int = 300
    parent_summary: str = ""; metadata: dict = field(default_factory=dict)

@dataclass
class TaskResult:
    task_id: str; status: TaskStatus; summary: str = ""
    artifacts: dict = field(default_factory=dict)
    full_trace: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0; tokens_used: int = 0; error: str = ""
    def to_dict(self):
        d = asdict(self); d["status"] = self.status.value; return d

class WorklogProtocol:
    def __init__(self, path: Path):
        self.path = path; self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Xeno Multi-Agent Worklog\n\n", encoding="utf-8")
    def read_prior(self, max_sections=10):
        try:
            content = self.path.read_text(encoding="utf-8")
            sections = content.split("\n---\n")[1:]
            return "\n---\n".join(sections[-max_sections:]) if sections else ""
        except: return ""
    def append_section(self, task_id, agent_name, task_description, work_log, stage_summary):
        section = f"---\nTask ID: {task_id}\nAgent: {agent_name}\nTask: {task_description}\n\nWork Log:\n{work_log}\n\nStage Summary:\n{stage_summary}\n"
        with self.path.open("a", encoding="utf-8") as f: f.write("\n"+section)

class SubAgentExecutor:
    def __init__(self, agent_runner, worklog, name="subagent"):
        self.agent_runner = agent_runner; self.worklog = worklog; self.name = name
    async def execute(self, ctx: TaskContext) -> TaskResult:
        result = TaskResult(task_id=ctx.task_id, status=TaskStatus.RUNNING)
        try:
            ctx.metadata["prior_worklog"] = self.worklog.read_prior(max_sections=5)
            raw = await asyncio.wait_for(self.agent_runner(ctx), timeout=ctx.budget_seconds)
            result.summary = (raw.get("summary","") if isinstance(raw, dict) else str(raw))[:2000]
            result.artifacts = raw.get("artifacts",{}) if isinstance(raw, dict) else {}
            result.full_trace = raw.get("trace",[]) if isinstance(raw, dict) else []
            result.tokens_used = raw.get("tokens_used",0) if isinstance(raw, dict) else 0
            result.completed_at = time.time(); result.status = TaskStatus.COMPLETED
            self.worklog.append_section(ctx.task_id, self.name, ctx.description,
                "\n".join(f"- {s.get('action','')}: {s.get('result','')[:80]}" for s in result.full_trace[-10:]) or "- (no steps)",
                result.summary[:500])
        except asyncio.TimeoutError:
            result.status = TaskStatus.TIMEOUT; result.completed_at = time.time()
            result.error = f"Timed out after {ctx.budget_seconds}s"
        except Exception as e:
            result.status = TaskStatus.FAILED; result.completed_at = time.time()
            result.error = str(e)
        return result

class SubAgentOrchestrator:
    def __init__(self, worklog_path: Path):
        self.worklog = WorklogProtocol(worklog_path)
        self.runners = {}; self.history = []; self._counter = 0
    def register(self, name, runner):
        self.runners[name] = SubAgentExecutor(runner, self.worklog, name)
    def _next_id(self, name):
        self._counter += 1; return f"{name}_{self._counter:04d}"
    async def spawn(self, agent_name, description, **kw):
        if agent_name not in self.runners: raise ValueError(f"Unknown: {agent_name}")
        ctx = TaskContext(task_id=self._next_id(agent_name), description=description, **kw)
        result = await self.runners[agent_name].execute(ctx)
        self.history.append(result); return result
    async def spawn_parallel(self, tasks, parent_id="main"):
        coros = [self.spawn(t["agent"], t["description"],
                   parent_id=t.get("parent_id",parent_id),
                   capability_slice=t.get("capability_slice"),
                   memory_slice=t.get("memory_slice"),
                   budget_tokens=t.get("budget_tokens",8000),
                   budget_seconds=t.get("budget_seconds",300)) for t in tasks]
        return await asyncio.gather(*coros)
    def stats(self):
        by_status = {}
        for r in self.history: by_status[r.status.value] = by_status.get(r.status.value,0)+1
        return {"total_spawned": len(self.history), "by_status": by_status,
                "registered_agents": list(self.runners.keys())}
