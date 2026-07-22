"""Git checkpoint — undo points."""
from __future__ import annotations
import logging, subprocess, time, uuid, json, shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
logger = logging.getLogger(__name__)

@dataclass
class Checkpoint:
    id: str; label: str; created_at: float
    git_tag: str = ""; files_changed: list[str] = field(default_factory=list)
    tool: str = ""; metadata: dict = field(default_factory=dict)
    def to_dict(self): return asdict(self)

class GitCheckpointer:
    def __init__(self, project_root: Path, data_dir: Path, max_checkpoints=100):
        self.root = project_root; self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.registry_path = self.data_dir / "checkpoints.json"
        self.sidecar_dir = self.data_dir / "snapshots"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        self._is_git = self._detect_git()
        self._registry = self._load()
    def _detect_git(self):
        try:
            r = subprocess.run(["git","rev-parse","--is-inside-work-tree"],
                cwd=str(self.root), capture_output=True, text=True, timeout=5)
            return r.returncode == 0 and r.stdout.strip() == "true"
        except: return False
    def _load(self):
        if not self.registry_path.exists(): return []
        try: return [Checkpoint(**d) for d in json.loads(self.registry_path.read_text(encoding="utf-8"))]
        except: return []
    def _save(self):
        self.registry_path.write_text(
            json.dumps([c.to_dict() for c in self._registry[-self.max_checkpoints:]], indent=2),
            encoding="utf-8")
    def checkpoint(self, label, tool="", files_changed=None, metadata=None):
        cp = Checkpoint(id=f"cp_{uuid.uuid4().hex[:8]}", label=label, created_at=time.time(),
                        files_changed=files_changed or [], tool=tool, metadata=metadata or {})
        if self._is_git:
            try:
                subprocess.run(["git","add","-A"], cwd=str(self.root), capture_output=True, timeout=10)
                tag = f"xeno-cp/{cp.id}"
                subprocess.run(["git","tag","-f",tag], cwd=str(self.root), capture_output=True, timeout=10)
                cp.git_tag = tag
            except: pass
        self._registry.append(cp)
        self._registry = self._registry[-self.max_checkpoints:]
        self._save(); return cp
    def undo_last(self):
        if not self._registry: return None
        cp = self._registry[-1]
        if self.restore(cp.id):
            self._registry.pop(); self._save(); return cp
        return None
    def restore(self, cp_id):
        cp = next((c for c in self._registry if c.id == cp_id), None)
        if not cp: return False
        if self._is_git and cp.git_tag:
            try:
                subprocess.run(["git","checkout",cp.git_tag,"--","."],
                    cwd=str(self.root), capture_output=True, timeout=30)
                return True
            except: return False
        return False
    def list_recent(self, n=20): return self._registry[-n:]
    def is_git(self): return self._is_git
    def stats(self): return {"total_checkpoints":len(self._registry), "is_git_repo":self._is_git}
