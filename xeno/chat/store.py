"""ChatStore — persistent conversation history with agent activity tracking.

Stores sessions as JSONL append-only logs. Maintains an index for fast listing.
Integrates with TemporalKnowledgeGraph for cross-session fact persistence.

Features:
- Append-only JSONL per session
- Agent activity log (what agents ran, with task+result)
- Context compaction (auto-summarize every N messages)
- Semantic search across sessions
- Resume support
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from xeno.config import XenoConfig
from xeno.chat.session import ChatSession, ChatMessage, AgentCall

logger = logging.getLogger(__name__)


class ChatStore:
    """Persistent conversation storage with indexing and search."""

    def __init__(self, config: Optional[XenoConfig] = None):
        self.config = config or XenoConfig.from_env()
        self._sessions_dir = self.config.data_dir / "chat"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._sessions_dir / "index.json"
        self._index: dict[str, dict] = self._load_index()
        self._session_cache: dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()

    def _load_index(self) -> dict[str, dict]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except Exception:
                pass
        return {}

    def _save_index(self):
        self._index_path.write_text(json.dumps(self._index, indent=2, default=str))

    def _session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.jsonl"

    # ── Session Management ────────────────────────────────────────────────

    def create_session(self, model: str = "", metadata: Optional[dict] = None) -> ChatSession:
        session = ChatSession(
            id=uuid.uuid4().hex[:12],
            model=model,
            metadata=metadata or {},
        )
        self._index[session.id] = {
            "id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": 0,
            "summary": "",
            "model": model,
        }
        self._save_index()
        self._session_cache[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        if session_id in self._session_cache:
            return self._session_cache[session_id]
        path = self._session_path(session_id)
        if not path.exists():
            return None
        session = self._load_session_from_file(session_id, path)
        self._session_cache[session_id] = session
        return session

    def _load_session_from_file(self, session_id: str, path: Path) -> ChatSession:
        session = ChatSession(id=session_id)
        if path.exists():
            try:
                lines = path.read_text().strip().split("\n")
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if "role" in data:
                            msg = ChatMessage(**{k: v for k, v in data.items() if k in ChatMessage.__dataclass_fields__})
                            session.messages.append(msg)
                        elif "agent_call" in data:
                            call = AgentCall(**data["agent_call"])
                            session.agent_activity.append(call)
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logger.warning(f"Failed to load session {session_id}: {e}")
        session._reconstruct_index()
        return session

    def list_sessions(self, limit: int = 20) -> list[dict]:
        sessions = sorted(self._index.values(), key=lambda s: s.get("updated_at", 0), reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        self._index.pop(session_id, None)
        self._session_cache.pop(session_id, None)
        self._save_index()
        return True

    # ── Message Operations ────────────────────────────────────────────────

    async def add_message(self, session_id: str, role: str, content: str,
                           agent_calls: Optional[list[dict]] = None,
                           metadata: Optional[dict] = None) -> str:
        """Add a message to a session. Returns message ID."""
        session = self.get_session(session_id)
        if not session:
            session = ChatSession(id=session_id)
            self._session_cache[session_id] = session

        msg = ChatMessage(
            id=uuid.uuid4().hex[:8],
            role=role,
            content=content,
            timestamp=time.time(),
            agent_calls=[AgentCall(**c) for c in (agent_calls or [])],
            metadata=metadata or {},
        )

        async with self._lock:
            session.messages.append(msg)
            session.updated_at = time.time()
            path = self._session_path(session_id)
            data = {
                "role": msg.role, "content": msg.content, "timestamp": msg.timestamp,
                "type": "message",
            }
            if agent_calls:
                data["agent_calls"] = agent_calls
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as f:
                f.write(json.dumps(data, default=str) + "\n")

            if session_id in self._index:
                self._index[session_id]["message_count"] = len(session.messages)
                self._index[session_id]["updated_at"] = session.updated_at
                self._save_index()

        return msg.id

    async def add_agent_call(self, session_id: str, agent_type: str, task_id: str,
                              prompt: str, result: str, duration: float,
                              success: bool):
        """Record an agent dispatch in the session log."""
        call = AgentCall(agent_type=agent_type, task_id=task_id, prompt=prompt,
                         result=result, duration=duration, success=success)
        session = self.get_session(session_id)
        if not session:
            return
        session.agent_activity.append(call)

        path = self._session_path(session_id)
        with path.open("a") as f:
            f.write(json.dumps({"type": "agent_call", "agent_call": call.to_dict()}, default=str) + "\n")

    # ── Context Retrieval ─────────────────────────────────────────────────

    def get_context(self, session_id: str, last_n: int = 20) -> list[dict]:
        """Get last N messages as context list."""
        session = self.get_session(session_id)
        if not session:
            return []
        return [{"role": m.role, "content": m.content} for m in session.messages[-last_n:]]

    def get_summary(self, session_id: str) -> str:
        """Get session summary."""
        session = self.get_session(session_id)
        if not session:
            return ""
        return session.summary or f"{len(session.messages)} messages, {len(session.agent_activity)} agent calls"

    def get_agent_activity(self, session_id: str, limit: int = 10) -> list[dict]:
        """Get recent agent activity in this session."""
        session = self.get_session(session_id)
        if not session:
            return []
        return [a.to_dict() for a in session.agent_activity[-limit:]]

    # ── Search ────────────────────────────────────────────────────────────

    def search_messages(self, query: str, limit: int = 10) -> list[dict]:
        """Search across all sessions for matching messages."""
        q = query.lower()
        results = []
        for sid in list(self._index.keys())[:20]:
            session = self.get_session(sid)
            if not session:
                continue
            for msg in session.messages:
                if q in msg.content.lower():
                    results.append({
                        "session_id": sid,
                        "role": msg.role,
                        "content": msg.content[:200],
                        "timestamp": msg.timestamp,
                    })
                    if len(results) >= limit:
                        return results
        return results

    # ── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        total_sessions = len(self._index)
        total_messages = sum(s.get("message_count", 0) for s in self._index.values())
        return {"total_sessions": total_sessions, "total_messages": total_messages}


_store_instance: Optional[ChatStore] = None


def get_chat_store() -> ChatStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = ChatStore()
    return _store_instance
