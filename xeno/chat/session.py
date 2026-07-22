"""Chat session data models for ChatStore."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentCall:
    """Record of an agent dispatch from this session."""
    agent_type: str
    task_id: str
    prompt: str = ""
    result: str = ""
    duration: float = 0.0
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "task_id": self.task_id,
            "prompt": self.prompt[:100],
            "result": self.result[:200],
            "duration": self.duration,
            "success": self.success,
        }


@dataclass
class ChatMessage:
    """A single message in a chat session."""
    id: str = ""
    role: str = "user"
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    agent_calls: list[AgentCall] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatSession:
    """A complete conversation session with message history and agent activity."""
    id: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    agent_activity: list[AgentCall] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    summary: str = ""
    model: str = ""
    metadata: dict = field(default_factory=dict)

    def _reconstruct_index(self):
        """Reconstruct internal state after loading from file."""
        pass
