"""Harness loop — heartbeat + recovery."""
from __future__ import annotations
import asyncio, json, logging, os, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from xeno.harness.feature_list import FeatureListManager
from xeno.harness.progress import ProgressTracker
from xeno.harness.git_checkpoint import GitCheckpointer
logger = logging.getLogger(__name__)

@dataclass
class Heartbeat:
    session_id: str; timestamp: float; status: str
    current_task: str = ""; pid: int = 0

class HarnessLoop:
    def __init__(self, data_dir, feature_list, progress, checkpointer,
                 heartbeat_interval=30.0, stall_timeout=300.0):
        self.data_dir = data_dir; self.data_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path = self.data_dir / "heartbeat.json"
        self.feature_list = feature_list; self.progress = progress
        self.checkpointer = checkpointer
        self.heartbeat_interval = heartbeat_interval
        self.stall_timeout = stall_timeout
        self.session_id = f"s_{int(time.time())}"
        self._heartbeat_task = None; self._stop = False
        self._status = "starting"; self._current_task = ""
    def start_session(self):
        self._status = "alive"; self._write_heartbeat()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    def end_session(self):
        self._stop = True
        if self._heartbeat_task: self._heartbeat_task.cancel()
        self._status = "shutdown"; self._write_heartbeat()
    def mark_working(self, task): self._status="working"; self._current_task=task; self._write_heartbeat()
    def mark_waiting(self): self._status="waiting_input"; self._write_heartbeat()
    def _write_heartbeat(self):
        hb = {"session_id":self.session_id,"timestamp":time.time(),"status":self._status,
              "current_task":self._current_task,"pid":os.getpid()}
        try: self.heartbeat_path.write_text(json.dumps(hb, indent=2), encoding="utf-8")
        except: pass
    async def _heartbeat_loop(self):
        while not self._stop:
            try: self._write_heartbeat()
            except: pass
            await asyncio.sleep(self.heartbeat_interval)
    def status(self):
        return {"session_id":self.session_id,"status":self._status,
                "current_task":self._current_task,
                "checkpoints": self.checkpointer.stats()}
