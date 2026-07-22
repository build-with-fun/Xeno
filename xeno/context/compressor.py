"""Context window compressor — sliding window + summarization for long conversations.

Prevents context limit issues by:
1. Keeping recent messages (sliding window)
2. Summarizing older messages into compressed context
3. Storing compressed chunks in vector memory for retrieval
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MessageCompressor:
    """Compress conversation history using sliding window + summarization.

    Usage:
        compressor = MessageCompressor(max_recent=20, llm=llm_func)
        messages = compressor.compress(messages)  # returns trimmed + summary
    """

    def __init__(
        self,
        max_recent: int = 20,
        max_tokens: int = 8000,
        llm: Optional[Any] = None,
    ):
        self.max_recent = max_recent
        self.max_tokens = max_tokens
        self.llm = llm
        self._summary: str = ""

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars per token)."""
        return len(text) // 4

    def compress(self, messages: list) -> list:
        """Compress a message list by sliding window + summary injection.

        Returns a new message list with:
        - System prompt (unchanged)
        - Summary of old context (if compressed)
        - Recent N messages (unchanged)
        """
        if not messages:
            return messages

        # Count total tokens
        total_text = " ".join(
            getattr(m, "content", str(m))[:100] if hasattr(m, "content") else str(m)[:100]
            for m in messages
        )
        if self.estimate_tokens(total_text) <= self.max_tokens:
            return messages

        # Keep system message + recent N
        system_msgs = [m for m in messages if getattr(m, "type", "") == "system"]
        recent_msgs = messages[-self.max_recent:] if len(messages) > self.max_recent else messages
        old_msgs = messages[len(system_msgs):-self.max_recent] if len(messages) > self.max_recent + len(system_msgs) else []

        if not old_msgs:
            return messages

        # Summarize old messages
        old_text = "\n".join(
            f"{getattr(m, 'type', 'user')}: {getattr(m, 'content', str(m))[:200]}"
            for m in old_msgs
        )
        self._summary = self._summarize(old_text)

        # Inject summary as system message
        summary_msg = type('obj', (object,), {
            'type': 'system',
            'content': f"[Compressed context]\n{self._summary}",
        })
        # Use dict format for compatibility
        summary_entry = {
            "role": "system",
            "content": f"[Previous conversation summary]\n{self._summary}",
        }

        result = system_msgs + [summary_entry] + recent_msgs
        logger.info(
            f"Context compressed: {len(messages)} → {len(result)} messages "
            f"(summary: {len(self._summary)} chars)"
        )
        return result

    def _summarize(self, text: str) -> str:
        """Summarize old conversation text."""
        if not text.strip():
            return ""
        if self.llm is None:
            # Fallback: extract key points heuristically
            lines = text.split("\n")
            key_lines = [l for l in lines if any(kw in l.lower() for kw in [
                "remember", "my name", "my birthday", "my favorite", "i am",
                "important", "project:", "task:", "goal:",
            ])]
            if key_lines:
                return "Key points from earlier:\n" + "\n".join(key_lines[-5:])
            return f"[{len(lines)} earlier messages]"

        try:
            import asyncio
            prompt = (
                "Summarize the following conversation in 2-3 sentences. "
                "Keep ALL facts/names/preferences. Output ONLY the summary.\n\n"
                f"{text[:3000]}"
            )
            result = self.llm("You are a conversation summarizer.", prompt)
            if asyncio.iscoroutine(result):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(result)
            return str(result)[:1000] if result else f"[{len(text)//100} earlier messages]"
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            return f"[{len(text)//100} earlier messages]"

    @property
    def summary(self) -> str:
        return self._summary

    def reset(self):
        self._summary = ""
