"""Skill Synthesiser — detects repeated patterns and generates new skills.

Monitors tool usage patterns and conversation topics. When a pattern
reaches a threshold (e.g., same 3 tools called in sequence 5+ times),
it generates a new SKILL.md file that bundles the operations into
a reusable skill.

This enables the system to grow its skill library organically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from xeno.config import XenoConfig

logger = logging.getLogger(__name__)


@dataclass
class PatternRecord:
    pattern: tuple[str, ...]
    count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    contexts: list[str] = field(default_factory=list)
    generated_skill: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "pattern": list(self.pattern),
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "generated_skill": self.generated_skill,
        }


@dataclass
class SynthesiserConfig:
    min_pattern_count: int = 5
    pattern_window_minutes: float = 60.0
    max_pattern_length: int = 5
    skills_dir: str = "skills"
    auto_enable: bool = True
    notify_main_agent: bool = True


class SkillSynthesiser:
    """Detects patterns and generates skills."""

    def __init__(self, config: Optional[SynthesiserConfig] = None,
                 data_dir: Optional[Path] = None):
        self.config = config or SynthesiserConfig()
        self.data_dir = data_dir or Path("data")
        self._tool_sequence: list[tuple[str, float]] = []
        self._patterns: dict[tuple[str, ...], PatternRecord] = {}
        self._skills_generated: int = 0
        self._last_prune: float = time.time()

    def record_tool_call(self, tool_name: str, context: Optional[str] = None):
        """Record a tool call for pattern detection."""
        now = time.time()
        self._tool_sequence.append((tool_name, now))

        # Prune old entries
        window = self.config.pattern_window_minutes * 60
        cutoff = now - window
        self._tool_sequence = [(t, ts) for t, ts in self._tool_sequence if ts > cutoff]

        # Update pattern counts
        self._update_patterns(tool_name, context, now)

    def _update_patterns(self, tool_name: str, context: Optional[str], now: float):
        """Update pattern counts from recent tool sequence."""
        max_len = self.config.max_pattern_length
        recent = [t for t, _ in self._tool_sequence[-max_len:]]

        for length in range(2, max_len + 1):
            if len(recent) < length:
                break
            pattern = tuple(recent[-length:])
            if pattern in self._patterns:
                record = self._patterns[pattern]
                record.count += 1
                record.last_seen = now
                if context:
                    record.contexts.append(context)
            else:
                self._patterns[pattern] = PatternRecord(
                    pattern=pattern,
                    count=1,
                    first_seen=now,
                    last_seen=now,
                    contexts=[context] if context else [],
                )

        # Prune old, non-generated patterns
        window = self.config.pattern_window_minutes * 60
        cutoff = now - window
        self._patterns = {
            k: v for k, v in self._patterns.items()
            if v.last_seen > cutoff or v.generated_skill is not None
        }

    def get_candidate_patterns(self) -> list[PatternRecord]:
        """Return patterns that exceed the threshold, sorted by count desc."""
        candidates = [
            p for p in self._patterns.values()
            if p.count >= self.config.min_pattern_count and p.generated_skill is None
        ]
        candidates.sort(key=lambda p: p.count, reverse=True)
        return candidates

    async def synthesize_skill(self, record: PatternRecord) -> Optional[Path]:
        """Generate a SKILL.md for a detected pattern."""
        pattern_name = "_".join(record.pattern)
        skill_name = f"auto_{pattern_name[:40].lower()}"

        skills_dir = Path(self.config.skills_dir)
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skills_dir / f"{skill_name}.md"

        # Collect context examples
        examples = record.contexts[-5:] if record.contexts else []
        example_text = "\n".join(f"  - {ctx}" for ctx in examples) if examples else "  - (auto-detected)"

        tools_list = "\n".join(f"  - `{t}`" for t in record.pattern)

        content = f"""---
name: {skill_name}
description: Auto-generated skill from repeated pattern `{' → '.join(record.pattern)}` (seen {record.count}x)
tools:
{chr(10).join(f'  - {t}' for t in record.pattern)}
auto_generated: true
original_count: {record.count}
---

# {skill_name}

## Description
Auto-synthesised from a repeated tool-use pattern detected {record.count} times.

## Pattern
{' → '.join(record.pattern)}

## Example Contexts
{example_text}

## Usage
This skill bundles a common sequence of tool calls into a reusable workflow.
The Main Agent can invoke this via `use_skill("{skill_name}")`.
"""

        skill_path.write_text(content, encoding="utf-8")
        record.generated_skill = skill_name
        self._skills_generated += 1

        logger.info(f"Synthesised skill '{skill_name}' from pattern {' → '.join(record.pattern)}")
        return skill_path

    async def synthesize_all_candidates(self) -> list[Path]:
        """Generate skills for all candidate patterns."""
        paths = []
        for record in self.get_candidate_patterns():
            path = await self.synthesize_skill(record)
            if path:
                paths.append(path)
        return paths

    def get_status(self) -> dict:
        return {
            "skills_generated": self._skills_generated,
            "tracked_patterns": len(self._patterns),
            "candidates": len(self.get_candidate_patterns()),
            "config": {
                "min_pattern_count": self.config.min_pattern_count,
                "pattern_window_minutes": self.config.pattern_window_minutes,
                "max_pattern_length": self.config.max_pattern_length,
            },
        }


_synthesiser_instance: Optional[SkillSynthesiser] = None


def get_synthesiser() -> SkillSynthesiser:
    global _synthesiser_instance
    if _synthesiser_instance is None:
        _synthesiser_instance = SkillSynthesiser()
    return _synthesiser_instance
