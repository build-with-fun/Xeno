"""Audit log — JSONL append-only."""
from __future__ import annotations
import json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
logger = logging.getLogger(__name__)

@dataclass
class AuditEntry:
    id: str; timestamp: float; event_type: str
    tool: str = ""; args_summary: str = ""; result_summary: str = ""
    risk_level: str = ""; approved_by: str = "auto"; session_id: str = ""
    duration_ms: int = 0; success: bool = True; error: str = ""
    metadata: dict = field(default_factory=dict)
    def to_dict(self): return asdict(self)

class AuditLog:
    def __init__(self, path: Path):
        self.path = path; self.path.parent.mkdir(parents=True, exist_ok=True)
    def log_tool_call(self, tool, args, result, risk_level="", approved_by="auto",
                      session_id="", duration_ms=0, success=True, error=""):
        e = AuditEntry(id=f"au_{uuid.uuid4().hex[:8]}", timestamp=time.time(), event_type="tool_call",
                       tool=tool, args_summary=str(args)[:300], result_summary=str(result)[:300],
                       risk_level=risk_level, approved_by=approved_by, session_id=session_id,
                       duration_ms=duration_ms, success=success, error=error[:500])
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(e.to_dict(), default=str)+"\n")
        except: pass
        return e
    def stats(self):
        return {"log_path": str(self.path)}
