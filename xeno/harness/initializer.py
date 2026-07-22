"""Harness initializer — runs on session start."""
from __future__ import annotations
import logging, time, subprocess, platform, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from xeno.harness.feature_list import FeatureListManager
from xeno.harness.progress import ProgressTracker
logger = logging.getLogger(__name__)

@dataclass
class SessionContext:
    user_intent: str = ""
    environment_summary: str = ""
    recent_progress: str = ""
    active_features: list[dict] = field(default_factory=list)
    suggested_next_action: str = ""
    timestamp: float = field(default_factory=time.time)
    def to_prompt_block(self):
        parts = ["=== SESSION CONTEXT ==="]
        if self.user_intent: parts.append(f"User intent: {self.user_intent}")
        if self.environment_summary: parts.append(f"Environment: {self.environment_summary}")
        if self.recent_progress: parts.append(f"Recent progress:\n{self.recent_progress}")
        if self.active_features:
            parts.append("Active features:")
            for f in self.active_features: parts.append(f"  - {f}")
        parts.append("=== END ===")
        return "\n".join(parts)

class HarnessInitializer:
    def __init__(self, workspace_root, data_dir, feature_list, progress):
        self.root = workspace_root; self.data_dir = data_dir
        self.feature_list = feature_list; self.progress = progress
    async def initialize(self) -> SessionContext:
        ctx = SessionContext()
        ctx.workspace_files = [p.name for p in sorted(self.root.iterdir()) if not p.name.startswith(".")][:30]
        ctx.environment_summary = self._scan_env()
        fl = self.feature_list.load()
        ctx.active_features = [{"name":f.name,"status":f.status.value,"description":f.description} for f in fl.active_features]
        ctx.recent_progress = self.progress.tail(10)
        ctx.user_intent = fl.user_intent_summary
        return ctx
    def _scan_env(self):
        parts = [f"OS={platform.system()} {platform.release()}", f"Python={sys.version.split()[0]}", f"CWD={self.root}"]
        for tool in ("git","node","python"):
            try:
                r = subprocess.run(["which",tool], capture_output=True, text=True, timeout=2)
                if r.returncode == 0: parts.append(f"{tool}=available")
            except: pass
        return ", ".join(parts)
