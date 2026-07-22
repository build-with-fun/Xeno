"""Context management system for Xeno.

Handles context window optimization: summarization, compression,
sliding window, and context offloading to long-term memory.
Following the deepagents guide's context management patterns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Tracks the current conversation context window."""
    messages: list[dict[str, str]] = field(default_factory=list)
    token_estimate: int = 0
    max_tokens: int = 8000
    summary: Optional[str] = None
    offloaded: list[dict[str, str]] = field(default_factory=list)

    @property
    def usage_ratio(self) -> float:
        return self.token_estimate / self.max_tokens if self.max_tokens > 0 else 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.token_estimate)


class ContextManager:
    """Manages the agent's context window for optimal performance.

    Implements:
    - Token-aware context tracking
    - Automatic summarization when context is near capacity
    - Sliding window for recent messages
    - Context offloading to long-term memory
    - Priority-based message retention
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        summarization_threshold: float = 0.75,
        offload_threshold: float = 0.9,
        keep_recent: int = 10,
    ):
        self.max_tokens = max_tokens
        self.summarization_threshold = summarization_threshold
        self.offload_threshold = offload_threshold
        self.keep_recent = keep_recent
        self.window = ContextWindow(max_tokens=max_tokens)
        self._summaries: list[str] = []

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    def add_message(self, role: str, content: str, priority: float = 0.5) -> dict[str, Any]:
        """Add a message to the context window."""
        tokens = self.estimate_tokens(content)
        msg = {
            "role": role,
            "content": content,
            "tokens": tokens,
            "priority": priority,
        }
        self.window.messages.append(msg)
        self.window.token_estimate += tokens

        # Check if we need to manage context
        if self.window.usage_ratio >= self.offload_threshold:
            self._offload()
        elif self.window.usage_ratio >= self.summarization_threshold:
            self._summarize_old()

        return msg

    def add_system_message(self, content: str) -> dict[str, Any]:
        """Add a system message (always retained, high priority)."""
        return self.add_message("system", content, priority=1.0)

    def get_messages(self, include_summary: bool = True) -> list[dict[str, str]]:
        """Get messages formatted for the model."""
        result = []

        # Include running summary if available
        if include_summary and self.window.summary:
            result.append({
                "role": "system",
                "content": f"Context from earlier conversation:\n{self.window.summary}",
            })

        # Add all current messages
        for msg in self.window.messages:
            result.append({"role": msg["role"], "content": msg["content"]})

        return result

    def get_recent(self, n: Optional[int] = None) -> list[dict[str, str]]:
        """Get the N most recent messages."""
        n = n or self.keep_recent
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.window.messages[-n:]
        ]

    def _summarize_old(self) -> None:
        """Summarize older messages to free up context space."""
        if len(self.window.messages) <= self.keep_recent:
            return

        # Split: keep recent, summarize old
        cutoff = len(self.window.messages) - self.keep_recent
        old_messages = self.window.messages[:cutoff]
        self.window.messages = self.window.messages[cutoff:]

        # Build summary of old messages
        old_text = "\n".join(
            f"{m['role']}: {m['content'][:200]}"
            for m in old_messages
        )
        summary = f"[Earlier context summary]: {old_text[:1000]}"

        self._summaries.append(summary)
        self.window.summary = "\n".join(self._summaries[-3:])  # Keep last 3 summaries

        # Recalculate tokens
        self.window.token_estimate = sum(m.get("tokens", 0) for m in self.window.messages)
        if self.window.summary:
            self.window.token_estimate += self.estimate_tokens(self.window.summary)

        logger.debug(f"Summarized {len(old_messages)} messages, context now: {self.window.token_estimate} tokens")

    def _offload(self) -> None:
        """Offload low-priority messages to long-term storage."""
        if len(self.window.messages) <= self.keep_recent:
            return

        # Sort by priority, offload lowest
        sorted_msgs = sorted(
            enumerate(self.window.messages[:-self.keep_recent]),
            key=lambda x: x[1].get("priority", 0.5),
        )

        offload_count = max(1, len(sorted_msgs) // 3)
        indices_to_offload = {idx for idx, _ in sorted_msgs[:offload_count]}

        new_messages = []
        for i, msg in enumerate(self.window.messages):
            if i in indices_to_offload:
                self.window.offloaded.append(msg)
            else:
                new_messages.append(msg)

        self.window.messages = new_messages
        self.window.token_estimate = sum(m.get("tokens", 0) for m in self.window.messages)

        logger.debug(f"Offloaded {len(indices_to_offload)} messages to storage")

    def clear(self) -> None:
        """Clear the context window."""
        self.window = ContextWindow(max_tokens=self.max_tokens)
        self._summaries.clear()

    def reset_with_context(self, messages: list[dict[str, str]]) -> None:
        """Reset the context window with new messages."""
        self.clear()
        for msg in messages:
            self.add_message(msg["role"], msg["content"])

    def get_offloaded(self) -> list[dict[str, str]]:
        """Get offloaded messages for potential recall."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.window.offloaded
        ]

    def recall_offloaded(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """Recall relevant offloaded messages."""
        query_words = set(query.lower().split())
        scored = []
        for msg in self.window.offloaded:
            content_words = set(msg["content"].lower().split())
            overlap = len(query_words & content_words)
            scored.append((overlap, msg))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"role": m["role"], "content": m["content"]}
            for _, m in scored[:limit]
        ]

    def stats(self) -> dict[str, Any]:
        """Get context window statistics."""
        return {
            "messages": len(self.window.messages),
            "tokens": self.window.token_estimate,
            "max_tokens": self.max_tokens,
            "usage": f"{self.window.usage_ratio:.1%}",
            "offloaded": len(self.window.offloaded),
            "summaries": len(self._summaries),
        }
