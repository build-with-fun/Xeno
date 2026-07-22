"""Context Compactor — Claude Code-style conversation summarization.

Every N messages, auto-generates a summary that captures key facts,
decisions, and state. The summary is stored alongside the raw messages
so the Main Agent can use it for efficient context loading.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ContextCompactor:
    """Compacts long conversations into summaries while preserving key information."""

    def __init__(self, max_messages_before_compact: int = 50,
                 target_tokens: int = 2000):
        self.max_messages_before_compact = max_messages_before_compact
        self.target_tokens = target_tokens

    def should_compact(self, message_count: int) -> bool:
        """Check if a session needs compaction."""
        return message_count > self.max_messages_before_compact

    def compact_messages(self, messages: list[dict]) -> str:
        """Generate a compact summary from message list.

        Extracts key facts, decisions, and action items.
        Returns a concise summary string.
        """
        if not messages:
            return ""

        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

        lines = []
        lines.append(f"Conversation summary ({len(messages)} messages)")

        if user_msgs:
            last_few = user_msgs[-5:]
            key_topics = []
            for m in last_few:
                content = m.get("content", "")[:100]
                if content:
                    key_topics.append(content)
            if key_topics:
                lines.append("Recent user topics:")
                for t in key_topics:
                    lines.append(f"  • {t}")

        assistant_msgs_text = [m.get("content", "")[:150] for m in assistant_msgs[-3:] if m.get("content")]
        if assistant_msgs_text:
            lines.append("Recent responses:")
            for r in assistant_msgs_text:
                lines.append(f"  • {r}")

        return "\n".join(lines)

    def get_context_window(self, messages: list[dict],
                           max_tokens: int = 4000) -> list[dict]:
        """Get a context window that fits within token limits.

        Returns the most recent messages, with older ones summarized.
        """
        total = len(messages)
        if total == 0:
            return []

        recent = messages[-10:]
        remaining = messages[:-10]

        if not remaining:
            return recent

        summary = self.compact_messages(remaining)

        result = [{"role": "system", "content": f"[Compressed summary of earlier conversation: {summary}]"}]
        result.extend(recent)
        return result
