from datetime import datetime
from typing import Any

from xeno.config import XenoConfig


class RealtimeMemory:
    """In-memory conversation history for the current session."""

    def __init__(self, config: XenoConfig, session_id: str = "default"):
        self.config = config
        self.session_id = session_id
        self.messages: list[dict[str, Any]] = []
        self.max_messages = 200

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content, "timestamp": datetime.now().isoformat()})
        self._trim()

    def add_ai_message(self, content: str, name: str | None = None) -> None:
        msg = {"role": "assistant", "content": content, "timestamp": datetime.now().isoformat()}
        if name:
            msg["name"] = name
        self.messages.append(msg)
        self._trim()

    def add_tool_result(self, tool_name: str, content: str) -> None:
        self.messages.append({"role": "tool", "tool_name": tool_name, "content": content, "timestamp": datetime.now().isoformat()})
        self._trim()

    def get_history(self, last_n: int | None = None) -> list[dict[str, Any]]:
        if last_n:
            return self.messages[-last_n:]
        return list(self.messages)

    def get_context_string(self, last_n: int = 20) -> str:
        recent = self.get_history(last_n)
        lines = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            name = msg.get("name", "")
            prefix = f"[{role}]"
            if name:
                prefix += f" ({name})"
            lines.append(f"{prefix} {content[:500]}")
        return "\n".join(lines)

    def clear(self) -> str:
        count = len(self.messages)
        self.messages.clear()
        return f"Cleared {count} messages from session '{self.session_id}'"

    def search(self, query: str) -> str:
        results = [m for m in self.messages if query.lower() in m.get("content", "").lower()]
        if not results:
            return f"No messages matching '{query}'"
        return "\n".join([f"[{m['role']}] {m['content'][:200]}" for m in results[-10:]])

    def _trim(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
