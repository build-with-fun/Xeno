"""Auto-compaction — keep context window from overflowing."""
from __future__ import annotations
import logging, time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
logger = logging.getLogger(__name__)

@dataclass
class CompactionResult:
    compacted: bool; original_tokens: int=0; new_tokens: int=0
    summary: str=""; preserved_turns: int=0; summarized_turns: int=0

class AutoCompactor:
    def __init__(self, max_tokens=200000, target_pct=0.7, preserve_recent=10):
        self.max_tokens=max_tokens; self.target_pct=target_pct; self.preserve_recent=preserve_recent
    def should_compact(self, messages, token_counter):
        return token_counter(messages) > self.max_tokens * self.target_pct
    async def compact_if_needed(self, messages, token_counter, summarizer):
        original = token_counter(messages)
        if original <= self.max_tokens * self.target_pct:
            return CompactionResult(False, original, original)
        return await self.compact(messages, token_counter, summarizer)
    async def compact(self, messages, token_counter, summarizer):
        original = token_counter(messages)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        recent = non_system[-self.preserve_recent:] if len(non_system) > self.preserve_recent else non_system
        to_summarize = non_system[:-self.preserve_recent] if len(non_system) > self.preserve_recent else []
        if not to_summarize:
            return CompactionResult(False, original, original)
        try: summary = await summarizer(to_summarize)
        except: summary = f"[Compacted {len(to_summarize)} messages]"
        summary_msg = {"role":"system","content":f"=== COMPACTED CONTEXT ===\n{summary}\n=== END ==="}
        new_messages = system_msgs + [summary_msg] + recent
        new_tokens = token_counter(new_messages)
        return CompactionResult(True, original, new_tokens, summary,
                                len(recent), len(to_summarize))

def estimate_tokens_simple(messages):
    total = 0
    for m in messages:
        c = m.get("content","")
        if isinstance(c, str): total += len(c)
        elif isinstance(c, list):
            for p in c: total += len(str(p.get("text",""))) if isinstance(p,dict) else 0
    return max(1, total // 4)

async def default_summarizer(messages):
    parts = [f"Summary of {len(messages)} prior messages:"]
    for m in messages[-5:]:
        c = m.get("content","")
        if isinstance(c, str): parts.append(f"  - {c[:120]}")
    return "\n".join(parts)
