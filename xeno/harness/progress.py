"""xeno-progress.txt — rolling log."""
from __future__ import annotations
import time, logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
logger = logging.getLogger(__name__)

@dataclass
class ProgressEntry:
    timestamp: float; tool: str; summary: str
    success: bool = True; duration_ms: int = 0
    def format_line(self):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        flag = "✓" if self.success else "✗"
        return f"[{ts}] {flag} {self.tool} — {self.summary} ({self.duration_ms}ms)"

class ProgressTracker:
    def __init__(self, data_dir: Path, max_lines=500):
        self.data_dir = data_dir; self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "xeno-progress.txt"
        self._buffer = deque(maxlen=max_lines)
    def record(self, tool, summary, success=True, duration_ms=0):
        e = ProgressEntry(time.time(), tool, summary[:200], success, duration_ms)
        self._buffer.append(e)
        try:
            with self.path.open("a", encoding="utf-8") as f: f.write(e.format_line()+"\n")
        except: pass
        return e
    def tail(self, n=10):
        items = list(self._buffer)[-n:]
        return "\n".join(e.format_line() for e in items) if items else "(no prior progress)"
    def stats(self):
        items = list(self._buffer)
        if not items: return {"total":0,"success_rate":0.0}
        return {"total":len(items), "success_rate":round(sum(1 for e in items if e.success)/len(items),3)}
