"""Task DAG — plans as directed acyclic graphs."""
from __future__ import annotations
import json, time, uuid, logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
logger = logging.getLogger(__name__)

class StepStatus(str, Enum):
    PENDING="pending"; READY="ready"; RUNNING="running"; COMPLETED="completed"
    FAILED="failed"; SKIPPED="skipped"; BLOCKED="blocked"
class StepType(str, Enum):
    ACTION="action"; SUB_AGENT="sub_agent"; DECISION="decision"
    PARALLEL_GROUP="parallel_group"; LOOP="loop"; CHECKPOINT="checkpoint"

@dataclass
class Step:
    id: str; name: str; description: str
    step_type: StepType = StepType.ACTION
    status: StepStatus = StepStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    tool: str = ""; tool_args: dict = field(default_factory=dict)
    sub_agent: str = ""; sub_agent_task: str = ""
    estimated_seconds: int = 30; actual_seconds: int = 0
    result: str = ""; error: str = ""; artifacts: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float = 0; completed_at: float = 0
    def to_dict(self):
        d = asdict(self); d["step_type"]=self.step_type.value; d["status"]=self.status.value; return d
    @classmethod
    def from_dict(cls, d):
        d={**d}
        if isinstance(d.get("step_type"),str): d["step_type"]=StepType(d["step_type"])
        if isinstance(d.get("status"),str): d["status"]=StepStatus(d["status"])
        return cls(**d)

@dataclass
class Plan:
    id: str; goal: str; description: str = ""
    steps: dict = field(default_factory=dict)
    root_steps: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "draft"
    def to_dict(self):
        return {"id":self.id,"goal":self.goal,"description":self.description,
                "steps":{sid:s.to_dict() for sid,s in self.steps.items()},
                "root_steps":self.root_steps,"created_at":self.created_at,
                "updated_at":self.updated_at,"status":self.status}
    @classmethod
    def from_dict(cls, d):
        p = cls(id=d["id"],goal=d["goal"],description=d.get("description",""),
                root_steps=d.get("root_steps",[]),created_at=d.get("created_at",time.time()),
                updated_at=d.get("updated_at",time.time()),status=d.get("status","draft"))
        for sid,sd in d.get("steps",{}).items(): p.steps[sid] = Step.from_dict(sd)
        return p

class PlanManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir; self.data_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir = self.data_dir / "plans"; self.plans_dir.mkdir(parents=True, exist_ok=True)
    def create_plan(self, goal, description=""):
        p = Plan(id=f"plan_{uuid.uuid4().hex[:8]}", goal=goal, description=description)
        self._save(p); return p
    def add_step(self, plan_id, name, description, step_type=StepType.ACTION, dependencies=None,
                 tool="", tool_args=None, sub_agent="", sub_agent_task="", estimated_seconds=30):
        plan = self.load_plan(plan_id)
        if plan is None: raise ValueError(f"Plan {plan_id} not found")
        s = Step(id=f"step_{uuid.uuid4().hex[:8]}", name=name, description=description,
                 step_type=step_type, dependencies=dependencies or [], tool=tool,
                 tool_args=tool_args or {}, sub_agent=sub_agent, sub_agent_task=sub_agent_task,
                 estimated_seconds=estimated_seconds)
        plan.steps[s.id] = s
        if not s.dependencies: plan.root_steps.append(s.id)
        plan.updated_at = time.time(); self._save(plan); return s
    def get_ready_steps(self, plan_id):
        plan = self.load_plan(plan_id)
        if plan is None: return []
        ready = []
        for s in plan.steps.values():
            if s.status != StepStatus.PENDING: continue
            if all(plan.steps[d].status == StepStatus.COMPLETED for d in s.dependencies if d in plan.steps):
                s.status = StepStatus.READY; ready.append(s)
        return ready
    def mark_step_completed(self, plan_id, step_id, result=""):
        plan = self.load_plan(plan_id)
        if plan is None: return
        if step_id in plan.steps:
            plan.steps[step_id].status = StepStatus.COMPLETED
            plan.steps[step_id].completed_at = time.time()
            plan.steps[step_id].result = result
            self._save(plan)
    def approve_plan(self, plan_id):
        plan = self.load_plan(plan_id)
        if plan is None: return False
        plan.status = "approved"; self._save(plan); return True
    def load_plan(self, plan_id):
        path = self.plans_dir / f"{plan_id}.json"
        if not path.exists(): return None
        try: return Plan.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except: return None
    def list_plans(self):
        plans = []
        for p in sorted(self.plans_dir.glob("plan_*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                plans.append({"id":d["id"],"goal":d["goal"],"status":d.get("status","draft"),
                              "steps":len(d.get("steps",{})),"created_at":d.get("created_at",0)})
            except: continue
        return plans
    def _save(self, plan):
        plan.updated_at = time.time()
        (self.plans_dir / f"{plan.id}.json").write_text(
            json.dumps(plan.to_dict(), indent=2, default=str), encoding="utf-8")
