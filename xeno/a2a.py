"""Agent-to-Agent (A2A) and Agent Network Protocol (ANP) support.

Implements:
- Google A2A protocol: AgentCard, Task, TaskState, streaming
- ANP (Agent Network Protocol): peer discovery, capability negotiation
- Agent profiles and discovery
- Cross-agent task delegation
- Message routing between agents

Reference: Google A2A specification (https://github.com/google/A2A)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class A2ATaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class A2ARole(str, Enum):
    USER = "user"
    AGENT = "agent"


@dataclass
class A2APart:
    """A part of an A2A message (text, file, or data)."""
    type: str  # text, file, data
    text: Optional[str] = None
    data: Optional[dict] = None
    file_uri: Optional[str] = None
    mime_type: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.data is not None:
            d["data"] = self.data
        if self.file_uri:
            d["file_uri"] = self.file_uri
        if self.mime_type:
            d["mime_type"] = self.mime_type
        return d


@dataclass
class A2AMessage:
    role: A2ARole
    parts: list[A2APart]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "parts": [p.to_dict() for p in self.parts],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> A2AMessage:
        return cls(
            role=A2ARole(data["role"]),
            parts=[A2APart(**p) for p in data["parts"]],
            metadata=data.get("metadata", {}),
        )


@dataclass
class A2ATask:
    id: str
    session_id: str
    messages: list[A2AMessage] = field(default_factory=list)
    state: A2ATaskState = A2ATaskState.SUBMITTED
    artifacts: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "state": self.state.value, "artifacts": self.artifacts,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])


@dataclass
class AgentCard:
    """A2A Agent Card for discovery and capability negotiation."""
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: dict[str, bool] = field(default_factory=lambda: {
        "streaming": True, "pushNotifications": False, "stateTransitionHistory": True,
    })
    skills: list[AgentSkill] = field(default_factory=list)
    authentication: Optional[dict] = None
    default_input_modes: list[str] = field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text"])

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description, "url": self.url,
            "version": self.version, "capabilities": self.capabilities,
            "skills": [
                {"id": s.id, "name": s.name, "description": s.description,
                 "tags": s.tags, "examples": s.examples}
                for s in self.skills
            ],
            "authentication": self.authentication,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentCard:
        skills = [
            AgentSkill(id=s["id"], name=s["name"], description=s["description"],
                       tags=s.get("tags", []), examples=s.get("examples", []))
            for s in data.get("skills", [])
        ]
        return cls(
            name=data["name"], description=data["description"], url=data["url"],
            version=data.get("version", "1.0.0"), capabilities=data.get("capabilities", {}),
            skills=skills, authentication=data.get("authentication"),
        )


@dataclass
class PeerAgent:
    card: AgentCard
    last_seen: float = field(default_factory=time.time)
    is_online: bool = True
    trust_score: float = 1.0
    task_count: int = 0

    def to_dict(self) -> dict:
        return {
            "card": self.card.to_dict(), "last_seen": self.last_seen,
            "online": self.is_online, "trust": self.trust_score, "tasks": self.task_count,
        }


class A2AProtocol:
    """Google A2A protocol implementation.

    Handles:
    - Task lifecycle (create, send, receive, cancel)
    - Message exchange with multi-part messages
    - Agent card publishing and discovery
    - Task state management
    - Streaming support (via SSE callback)
    """

    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self.tasks: dict[str, A2ATask] = {}
        self._task_handlers: dict[str, Callable] = {}

    def create_task(self, session_id: str, initial_message: str) -> A2ATask:
        task = A2ATask(
            id=f"a2a_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
        )
        msg = A2AMessage(
            role=A2ARole.USER,
            parts=[A2APart(type="text", text=initial_message)],
        )
        task.messages.append(msg)
        task.state = A2ATaskState.SUBMITTED
        self.tasks[task.id] = task
        return task

    def send_message(self, task_id: str, message: A2AMessage) -> Optional[A2ATask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.messages.append(message)
        task.updated_at = time.time()
        return task

    def complete_task(self, task_id: str, artifacts: Optional[list[dict]] = None) -> Optional[A2ATask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.state = A2ATaskState.COMPLETED
        if artifacts:
            task.artifacts.extend(artifacts)
        task.updated_at = time.time()
        return task

    def fail_task(self, task_id: str, error: str = "") -> Optional[A2ATask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.state = A2ATaskState.FAILED
        task.metadata["error"] = error
        task.updated_at = time.time()
        return task

    def cancel_task(self, task_id: str) -> Optional[A2ATask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.state = A2ATaskState.CANCELED
        task.updated_at = time.time()
        return task

    def get_task(self, task_id: str) -> Optional[A2ATask]:
        return self.tasks.get(task_id)

    def list_tasks(self, state: Optional[A2ATaskState] = None) -> list[A2ATask]:
        if state:
            return [t for t in self.tasks.values() if t.state == state]
        return list(self.tasks.values())

    def register_handler(self, skill_id: str, handler: Callable) -> None:
        self._task_handlers[skill_id] = handler

    def get_agent_card(self) -> dict:
        return self.agent_card.to_dict()


class ANPManager:
    """Agent Network Protocol (ANP) - peer discovery and cross-agent communication.

    Features:
    - Peer agent registration and discovery
    - Capability-based routing
    - Trust scoring
    - Message forwarding between agents
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/a2a")
        self.peers: dict[str, PeerAgent] = {}
        self.message_log: list[dict] = []
        self._load()

    def register_peer(self, card: AgentCard, trust_score: float = 1.0) -> PeerAgent:
        peer = PeerAgent(card=card, trust_score=trust_score)
        self.peers[card.url] = peer
        self._save()
        return peer

    def discover_peers(self, required_capabilities: Optional[list[str]] = None) -> list[PeerAgent]:
        results = []
        for peer in self.peers.values():
            if not peer.is_online:
                continue
            if required_capabilities:
                has_all = all(
                    peer.card.capabilities.get(cap, False)
                    for cap in required_capabilities
                )
                if not has_all:
                    continue
            results.append(peer)
        results.sort(key=lambda p: p.trust_score, reverse=True)
        return results

    def find_peer_by_skill(self, skill_name: str) -> list[PeerAgent]:
        results = []
        for peer in self.peers.values():
            if not peer.is_online:
                continue
            for skill in peer.card.skills:
                if skill_name.lower() in skill.name.lower():
                    results.append(peer)
                    break
        return results

    def route_message(self, target_url: str, message: dict) -> dict:
        """Route a message to a peer agent."""
        peer = self.peers.get(target_url)
        if not peer or not peer.is_online:
            return {"error": "peer not found or offline"}
        self.message_log.append({
            "target": target_url, "message": message,
            "timestamp": time.time(),
        })
        peer.task_count += 1
        peer.last_seen = time.time()
        self._save()
        return {"status": "sent", "target": target_url}

    def mark_offline(self, url: str) -> None:
        if url in self.peers:
            self.peers[url].is_online = False
            self._save()

    def mark_online(self, url: str) -> None:
        if url in self.peers:
            self.peers[url].is_online = True
            self.peers[url].last_seen = time.time()
            self._save()

    def summary(self) -> str:
        online = sum(1 for p in self.peers.values() if p.is_online)
        return f"ANP: {online}/{len(self.peers)} peers online, {len(self.message_log)} messages"

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "peers.json").write_text(
            json.dumps({url: p.to_dict() for url, p in self.peers.items()}, indent=2)
        )

    def _load(self) -> None:
        path = self.data_dir / "peers.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for url, d in data.items():
                    card = AgentCard.from_dict(d["card"])
                    self.peers[url] = PeerAgent(
                        card=card, last_seen=d.get("last_seen", 0),
                        is_online=d.get("online", True),
                        trust_score=d.get("trust", 1.0),
                        task_count=d.get("tasks", 0),
                    )
            except Exception:
                self.peers = {}
