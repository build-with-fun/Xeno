from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class ContextCompressor:
    def __init__(self, max_tokens: int = 32000, target_tokens: int = 24000):
        self.max_tokens = max_tokens
        self.target_tokens = target_tokens

    def compress(self, text: str, priority_regions: Optional[list[tuple[int, int]]] = None) -> str:
        estimated = len(text) // 4
        if estimated <= self.target_tokens:
            return text

        logger.info(f"Compressing context: ~{estimated} tokens (target: {self.target_tokens})")

        if priority_regions:
            kept = []
            remaining = estimated
            for start, end in sorted(priority_regions, key=lambda x: x[1] - x[0], reverse=True):
                segment = text[start:end]
                segment_tokens = len(segment) // 4
                if remaining - segment_tokens >= self.target_tokens * 0.7:
                    kept.append((start, segment))
                    remaining -= segment_tokens
            if kept:
                kept.sort(key=lambda x: x[0])
                result = "\n\n[...]\n\n".join(k[1] for k in kept)
                return result[: self.target_tokens * 4]

        lines = text.split("\n")
        if len(lines) > 200:
            lines = self._summarize_lines(lines)

        compressed = "\n".join(lines)
        if len(compressed) // 4 > self.max_tokens:
            compressed = compressed[: self.max_tokens * 4]
        return compressed

    def _summarize_lines(self, lines: list[str]) -> list[str]:
        HEAD_KEEP = 60
        TAIL_KEEP = 40

        if len(lines) <= HEAD_KEEP + TAIL_KEEP:
            return lines

        result = lines[:HEAD_KEEP]
        result.append(f"\n... [{len(lines) - HEAD_KEEP - TAIL_KEEP} lines omitted by compressor] ...\n")
        result.extend(lines[-TAIL_KEEP:])
        return result

    def extract_code_blocks(self, text: str) -> list[str]:
        return re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)

    def remove_redundant_whitespace(self, text: str) -> str:
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r" {4,}", " ", text)
        return text.strip()
