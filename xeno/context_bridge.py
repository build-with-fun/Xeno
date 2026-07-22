"""Context Bridge — shares activity summaries between 24/7 agents and the main brain.

Always-on agents (WhatsApp, Gmail, etc.) write task summaries here.
The brain orchestrator queries this bridge when the user asks about agent activity.

Usage:
  bridge = AgentContextBridge(data_dir)
  bridge.add_entry("whatsapp", "message_received", "Mr Banda said hello", participants=["Mr Banda"])
  summary = bridge.get_agent_summary("whatsapp")
  pending = bridge.get_pending_approvals()
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentActivityEntry:
    agent_name: str
    entry_type: str
    summary: str
    detail: str = ""
    participants: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    needs_approval: bool = False
    approval_status: str = "none"
    approval_id: str = ""


class AgentContextBridge:
    """Stores and retrieves context from all 24/7 agents."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[AgentActivityEntry] = []
        self._load()

    def _entries_file(self, agent_name: str) -> Path:
        return self.data_dir / f"{agent_name}_context.json"

    def _load(self):
        for f in self.data_dir.glob("*_context.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for item in data:
                    self._entries.append(AgentActivityEntry(**item))
            except Exception as e:
                logger.warning(f"Failed to load context from {f}: {e}")

    def _save(self, agent_name: str):
        entries = [e for e in self._entries if e.agent_name == agent_name]
        f = self._entries_file(agent_name)
        f.write_text(
            json.dumps([asdict(e) for e in entries[-500:]], indent=2, default=str),
            encoding="utf-8",
        )

    def add_entry(
        self,
        agent_name: str,
        entry_type: str,
        summary: str,
        detail: str = "",
        participants: list[str] | None = None,
        metadata: dict | None = None,
        needs_approval: bool = False,
    ) -> str:
        entry_id = f"ctx_{int(time.time() * 1000)}_{len(self._entries)}"
        entry = AgentActivityEntry(
            agent_name=agent_name,
            entry_type=entry_type,
            summary=summary,
            detail=detail,
            participants=participants or [],
            metadata=metadata or {},
            needs_approval=needs_approval,
            approval_id=entry_id if needs_approval else "",
            approval_status="pending" if needs_approval else "none",
        )
        self._entries.append(entry)
        self._save(agent_name)
        if len(self._entries) > 5000:
            self._entries = self._entries[-3000:]
        return entry_id

    def get_recent(self, agent_name: str, limit: int = 20) -> list[AgentActivityEntry]:
        entries = [e for e in self._entries if e.agent_name == agent_name]
        return entries[-limit:]

    def query_context(self, agent_name: str, query: str, limit: int = 10) -> list[AgentActivityEntry]:
        query_lower = query.lower()
        matches = []
        for e in self._entries:
            if e.agent_name != agent_name:
                continue
            if (
                query_lower in e.summary.lower()
                or query_lower in e.detail.lower()
                or any(query_lower in p.lower() for p in e.participants)
            ):
                matches.append(e)
        return matches[-limit:]

    def get_all_agents(self) -> list[str]:
        return sorted(set(e.agent_name for e in self._entries))

    def get_pending_approvals(self, agent_name: str = "") -> list[AgentActivityEntry]:
        entries = [e for e in self._entries if e.approval_status == "pending"]
        if agent_name:
            entries = [e for e in entries if e.agent_name == agent_name]
        return entries

    def approve(self, approval_id: str) -> bool:
        for e in self._entries:
            if e.approval_id == approval_id:
                e.approval_status = "approved"
                e.needs_approval = False
                self._save(e.agent_name)
                return True
        return False

    def reject(self, approval_id: str) -> bool:
        for e in self._entries:
            if e.approval_id == approval_id:
                e.approval_status = "rejected"
                e.needs_approval = False
                self._save(e.agent_name)
                return True
        return False

    def get_agent_summary(self, agent_name: str, limit: int = 10) -> str:
        entries = self.get_recent(agent_name, limit=50)
        if not entries:
            return f"No recent activity for '{agent_name}'."
        pending = sum(1 for e in entries if e.approval_status == "pending")
        lines = [f"Recent {agent_name} activity ({len(entries)} entries, {pending} pending approval):"]
        for e in reversed(entries[-limit:]):
            ts = time.strftime("%H:%M", time.localtime(e.timestamp))
            part = f" ({', '.join(e.participants[:3])})" if e.participants else ""
            flag = " [PENDING]" if e.approval_status == "pending" else ""
            lines.append(f"  [{ts}] [{e.entry_type}] {e.summary}{part}{flag}")
        return "\n".join(lines)

    def summary(self) -> dict:
        agents = self.get_all_agents()
        return {
            "total_entries": len(self._entries),
            "agents": agents,
            "pending_approvals": len(self.get_pending_approvals()),
        }
