"""Unified memory reconciliation — AUDN lifecycle."""
from __future__ import annotations
import json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
logger = logging.getLogger(__name__)

class ReconcileAction(str, Enum):
    ADD="add"; UPDATE="update"; DELETE="delete"; NOOP="noop"; SPLIT="split"
class MemoryTier(str, Enum):
    WORKING="working"; EPISODIC="episodic"; SEMANTIC="semantic"; PROCEDURAL="procedural"

@dataclass
class ReconcileDecision:
    action: ReconcileAction; target_tier: MemoryTier
    existing_id: str=""; reason: str=""; confidence: float=0.5

class MemoryReconciler:
    def __init__(self, data_dir, llm_judge=None, storage_backends=None):
        self.data_dir = data_dir; self.data_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_judge; self.backends = storage_backends or {}
        self._stats = {"add":0,"update":0,"delete":0,"noop":0,"split":0}
    def register_backend(self, tier, backend): self.backends[tier] = backend
    async def reconcile(self, content, suggested_tier=MemoryTier.SEMANTIC, **kw):
        existing = self._find_existing(content, suggested_tier)
        if not existing:
            d = ReconcileDecision(ReconcileAction.ADD, suggested_tier, reason="no existing", confidence=0.9)
        else:
            top = existing[0]; sim = top.get("score",0)
            if sim > 0.95: d = ReconcileDecision(ReconcileAction.NOOP, suggested_tier, top["id"], "already stored", 0.8)
            elif sim > 0.7: d = ReconcileDecision(ReconcileAction.UPDATE, suggested_tier, top["id"], "extending", 0.7)
            else: d = ReconcileDecision(ReconcileAction.ADD, suggested_tier, reason="distinct", confidence=0.85)
        await self._execute(d, content, suggested_tier, **kw)
        self._stats[d.action.value] = self._stats.get(d.action.value,0)+1
        return d
    def _find_existing(self, content, tier):
        results = []
        backend = self.backends.get(tier)
        if backend and hasattr(backend, "search"):
            try:
                found = backend.search(content, limit=3)
                for m in found if isinstance(found, list) else []:
                    results.append({"id": getattr(m,"id","") or (m.get("id","") if isinstance(m,dict) else ""),
                                    "content": getattr(m,"content","") or (m.get("content","") if isinstance(m,dict) else ""),
                                    "score": getattr(m,"score",0.5)})
            except: pass
        return results
    async def _execute(self, decision, content, tier, **kw):
        backend = self.backends.get(decision.target_tier)
        if backend is None: return
        try:
            if decision.action == ReconcileAction.ADD and hasattr(backend, "store"):
                backend.store(content, **{k:v for k,v in kw.items() if k in ("metadata","tags","importance")})
            elif decision.action == ReconcileAction.UPDATE and hasattr(backend, "update"):
                backend.update(decision.existing_id, content)
        except: pass
    def stats(self): return {"total_decisions": sum(self._stats.values()), "by_action": dict(self._stats)}
