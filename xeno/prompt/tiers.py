from __future__ import annotations

import hashlib
import json
import logging
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TierCache:
    identity_hash: str = ""
    identity_prompt: str = ""
    metadata_hash: str = ""
    metadata_prompt: str = ""
    instructions_hash: str = ""
    instructions_prompt: str = ""
    context_hash: str = ""
    context_prompt: str = ""
    last_built: float = 0.0
    build_count: int = 0


class PromptTierBuilder:
    """Enhanced prompt tier builder with Hermes-style caching."""

    def __init__(self):
        self._cache = TierCache()
        self._identity_config: dict = {}
        self._tool_registry: list[dict] = []
        self._skill_descriptions: list[str] = []
        self._capability_list: list[str] = []
        self._instructions_version: int = 0
        self._soul_content: str = ""
        self._memory_content: str = ""

    def configure_identity(self, **kwargs):
        self._identity_config = kwargs
        self._cache.identity_hash = ""

    def set_tools(self, tools: list[dict]):
        self._tool_registry = tools
        self._cache.instructions_hash = ""

    def set_skills(self, skills: list[str]):
        self._skill_descriptions = skills
        self._cache.instructions_hash = ""

    def set_capabilities(self, caps: list[str]):
        self._capability_list = caps
        self._cache.instructions_hash = ""

    def set_soul(self, content: str):
        self._soul_content = content
        self._cache.identity_hash = ""

    def set_memory(self, content: str):
        self._memory_content = content
        self._cache.context_hash = ""

    def bump_instructions(self):
        self._instructions_version += 1
        self._cache.instructions_hash = ""

    def _build_identity(self) -> str:
        if self._cache.identity_hash:
            return self._cache.identity_prompt

        if self._soul_content:
            self._cache.identity_prompt = self._soul_content
            self._cache.identity_hash = hashlib.md5(self._soul_content.encode()).hexdigest()[:16]
            return self._cache.identity_prompt

        cfg = self._identity_config
        parts = [
            f"You are {cfg.get('name', 'Xeno')} — an autonomous AI agent.",
        ]
        if cfg.get("description"):
            parts.append(cfg["description"])
        parts.append(f"OS: {cfg.get('os', platform.system())} ({cfg.get('platform', platform.machine())})")
        parts.append(f"Python: {cfg.get('python_version', sys.version.split()[0])}")
        parts.append(f"Working directory: {cfg.get('cwd', Path.cwd())}")

        self._cache.identity_prompt = "\n".join(parts)
        self._cache.identity_hash = hashlib.md5(self._cache.identity_prompt.encode()).hexdigest()[:16]
        return self._cache.identity_prompt

    def _build_metadata(self, user_name: str = "", session_id: str = "") -> str:
        now_str = datetime.now(timezone.utc).isoformat()
        return "\n".join([
            f"Current time (UTC): {now_str}",
            f"User: {user_name or 'unknown'}",
            f"Session: {session_id or 'default'}",
        ])

    def _build_instructions(self) -> str:
        if self._cache.instructions_hash:
            return self._cache.instructions_prompt

        parts = []
        if self._tool_registry:
            tool_lines = []
            for t in self._tool_registry:
                name = t.get("name", "?")
                desc = t.get("description", "")[:80]
                tool_lines.append(f"  - {name}: {desc}")
            parts.append(f"Available tools ({len(self._tool_registry)}):\n" + "\n".join(tool_lines))
        if self._skill_descriptions:
            parts.append(f"Available skills ({len(self._skill_descriptions)}):\n" + "\n".join(f"  - {s}" for s in self._skill_descriptions))
        if self._capability_list:
            parts.append(f"Capabilities: {', '.join(self._capability_list)}")

        self._cache.instructions_prompt = "\n\n".join(parts)
        self._cache.instructions_hash = hashlib.md5(self._cache.instructions_prompt.encode()).hexdigest()[:16]
        return self._cache.instructions_prompt

    def _build_working(self, user_message: str, context: Optional[list[dict]] = None, profile: Optional[dict] = None) -> str:
        parts = [f"User message: {user_message}"]
        if profile:
            pref = {k: v for k, v in profile.items() if k in ("name", "preferences", "goals")}
            if pref:
                parts.append(f"User profile: {json.dumps(pref, default=str)[:500]}")
        if context:
            ctx_strs = []
            for c in context[-8:]:
                role = c.get("role", "?")
                content = str(c.get("content", ""))[:300]
                ctx_strs.append(f"[{role}] {content}")
            if ctx_strs:
                parts.append(f"Recent context ({len(ctx_strs)} messages):\n" + "\n".join(ctx_strs))
        return "\n\n".join(parts)

    def build_prompt(
        self,
        user_message: str,
        user_name: str = "",
        session_id: str = "",
        context: Optional[list[dict]] = None,
        profile: Optional[dict] = None,
        include_identity: bool = True,
        include_metadata: bool = True,
        include_instructions: bool = True,
    ) -> str:
        layers = []
        if include_identity:
            layers.append(self._build_identity())
        if include_metadata:
            layers.append(self._build_metadata(user_name, session_id))
        if include_instructions:
            layers.append(self._build_instructions())
        layers.append(self._build_working(user_message, context, profile))

        prompt = "\n\n---\n\n".join(layers)
        self._cache.last_built = time.time()
        self._cache.build_count += 1
        return prompt

    def estimate_tokens(self, prompt: str) -> int:
        return len(prompt) // 4

    @property
    def cache_stats(self) -> dict:
        return {
            "identity_cached": bool(self._cache.identity_hash),
            "instructions_cached": bool(self._cache.instructions_hash),
            "last_built": self._cache.last_built,
            "build_count": self._cache.build_count,
        }

    def invalidate(self):
        self._cache = TierCache()
        self._instructions_version += 1
