"""feature_list.json — current work state."""
from __future__ import annotations
import json, time, uuid, logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
logger = logging.getLogger(__name__)

class FeatureStatus(str, Enum):
    PLANNING="planning"; IN_PROGRESS="in_progress"; BLOCKED="blocked"
    REVIEW="review"; DONE="done"; ABANDONED="abandoned"

@dataclass
class Feature:
    id: str; name: str; description: str
    status: FeatureStatus = FeatureStatus.PLANNING
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    files: list[str] = field(default_factory=list)
    sub_steps: list[dict] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    def to_dict(self):
        d = asdict(self); d["status"]=self.status.value; return d
    @classmethod
    def from_dict(cls, d):
        d={**d}
        if isinstance(d.get("status"),str): d["status"]=FeatureStatus(d["status"])
        return cls(**d)

@dataclass
class FeatureList:
    version: str = "1.0"
    last_updated: float = field(default_factory=time.time)
    active_features: list[Feature] = field(default_factory=list)
    pending_tasks: list[dict] = field(default_factory=list)
    completed_recently: list[dict] = field(default_factory=list)
    user_intent_summary: str = ""
    def to_dict(self):
        return {"version":self.version,"last_updated":self.last_updated,
                "active_features":[f.to_dict() for f in self.active_features],
                "pending_tasks":self.pending_tasks,
                "completed_recently":self.completed_recently,
                "user_intent_summary":self.user_intent_summary}
    @classmethod
    def from_dict(cls, d):
        return cls(version=d.get("version","1.0"),
                   last_updated=d.get("last_updated",time.time()),
                   active_features=[Feature.from_dict(f) for f in d.get("active_features",[])],
                   pending_tasks=d.get("pending_tasks",[]),
                   completed_recently=d.get("completed_recently",[]),
                   user_intent_summary=d.get("user_intent_summary",""))

class FeatureListManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "feature_list.json"
        self._state: Optional[FeatureList] = None
    def load(self):
        if not self.path.exists():
            self._state = FeatureList(); self.save(); return self._state
        try:
            self._state = FeatureList.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
            return self._state
        except Exception:
            self._state = FeatureList(); self.save(); return self._state
    def save(self):
        if self._state is None: return
        self._state.last_updated = time.time()
        self.path.write_text(json.dumps(self._state.to_dict(), indent=2, default=str), encoding="utf-8")
    @property
    def state(self):
        if self._state is None: return self.load()
        return self._state
    def add_feature(self, name, description, files=None):
        f = Feature(id=f"f_{uuid.uuid4().hex[:8]}", name=name, description=description, files=files or [])
        self.state.active_features.append(f); self.save(); return f
    def set_user_intent(self, s):
        self.state.user_intent_summary = s; self.save()
    def get_context_block(self):
        s = self.state; lines = []
        if s.user_intent_summary: lines.append(f"Current work: {s.user_intent_summary}")
        for f in s.active_features:
            lines.append(f"  - [{f.status.value}] {f.name}: {f.description[:80]}")
        return "\n".join(lines) if lines else "No active work."
