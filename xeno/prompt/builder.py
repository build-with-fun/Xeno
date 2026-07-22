from __future__ import annotations

import hashlib
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from xeno.prompt.layers import (
    PromptLayer,
    LayerType,
    SOUL_MD_TEMPLATE,
    MEMORY_MD_TEMPLATE,
)

logger = logging.getLogger(__name__)


class PromptAssembly:
    def __init__(self, layers: list[PromptLayer]):
        self.layers = layers
        self.assembled_at = time.time()

    @property
    def full_prompt(self) -> str:
        return "\n\n---\n\n".join(l.content for l in self.layers)

    @property
    def token_estimate(self) -> int:
        return len(self.full_prompt) // 4

    @property
    def layer_summary(self) -> list[dict]:
        return [
            {"type": l.type.value, "length": len(l.content), "cached": bool(l.cache_key)}
            for l in self.layers
        ]


class PromptBuilder:
    def __init__(self):
        self._layer_cache: dict[LayerType, tuple[str, int]] = {}
        self._soul_content: str = ""
        self._memory_content: str = ""
        self._project_content: str = ""
        self._skills_index: list[str] = []
        self._tool_registry: list[dict] = []
        self._capability_list: list[str] = []
        self._instructions_version: int = 0
        self._build_count: int = 0

    def load_soul(self, path: str | Path = "SOUL.md") -> bool:
        p = Path(path)
        if p.exists():
            self._soul_content = p.read_text(encoding="utf-8")
            return True
        return False

    def load_memory(self, path: str | Path = "MEMORY.md") -> bool:
        p = Path(path)
        if p.exists():
            self._memory_content = p.read_text(encoding="utf-8")
            return True
        return False

    def load_project_context(self, path: str | Path = "AGENTS.md") -> bool:
        p = Path(path)
        if p.exists():
            self._project_content = p.read_text(encoding="utf-8")
            return True
        return False

    def set_soul_content(self, content: str):
        self._soul_content = content
        self._layer_cache.pop(LayerType.SOUL, None)

    def set_memory_content(self, content: str):
        self._memory_content = content
        self._layer_cache.pop(LayerType.MEMORY, None)

    def set_project_content(self, content: str):
        self._project_content = content
        self._layer_cache.pop(LayerType.PROJECT, None)

    def set_skills_index(self, skills: list[str]):
        self._skills_index = skills
        self._layer_cache.pop(LayerType.SKILLS_INDEX, None)

    def set_tools(self, tools: list[dict]):
        self._tool_registry = tools
        self._layer_cache.pop(LayerType.INSTRUCTIONS, None)
        self._instructions_version += 1

    def set_capabilities(self, caps: list[str]):
        self._capability_list = caps
        self._layer_cache.pop(LayerType.INSTRUCTIONS, None)
        self._instructions_version += 1

    def bump_instructions(self):
        self._instructions_version += 1
        self._layer_cache.pop(LayerType.INSTRUCTIONS, None)

    def _build_soul_layer(self) -> PromptLayer:
        cache_key = f"soul_v{hashlib.md5(self._soul_content.encode()).hexdigest()[:16]}"
        cached = self._layer_cache.get(LayerType.SOUL)
        if cached and cached[0] == cache_key:
            return PromptLayer(LayerType.SOUL, cached[1], version=1, cache_key=cache_key)

        content = self._soul_content or SOUL_MD_TEMPLATE.format(
            os_name=f"{platform.system()} {platform.release()}",
            platform=platform.platform(),
            cwd=Path.cwd(),
            python_version=sys.version.split()[0],
        )
        self._layer_cache[LayerType.SOUL] = (cache_key, content)
        return PromptLayer(LayerType.SOUL, content, version=1, cache_key=cache_key, persistent=True)

    def _build_memory_layer(self) -> PromptLayer:
        if self._memory_content:
            cache_key = f"mem_v{hashlib.md5(self._memory_content.encode()).hexdigest()[:16]}"
            return PromptLayer(LayerType.MEMORY, self._memory_content, version=1, cache_key=cache_key, persistent=True)
        return PromptLayer(LayerType.MEMORY, "", version=0, cache_key="", persistent=True)

    def _build_project_layer(self) -> PromptLayer:
        if self._project_content:
            cache_key = f"proj_v{hashlib.md5(self._project_content.encode()).hexdigest()[:16]}"
            cached = self._layer_cache.get(LayerType.PROJECT)
            if cached and cached[0] == cache_key:
                return PromptLayer(LayerType.PROJECT, cached[1], version=1, cache_key=cache_key)
            self._layer_cache[LayerType.PROJECT] = (cache_key, self._project_content)
            return PromptLayer(LayerType.PROJECT, self._project_content, version=1, cache_key=cache_key, persistent=True)
        return PromptLayer(LayerType.PROJECT, "", version=0, cache_key="", persistent=True)

    def _build_metadata_layer(self, user_name: str = "", session_id: str = "") -> PromptLayer:
        now = datetime.now(timezone.utc).isoformat()
        parts = [
            f"Time (UTC): {now}",
            f"User: {user_name or 'unknown'}",
            f"Session: {session_id or 'default'}",
        ]
        content = "\n".join(parts)
        return PromptLayer(LayerType.METADATA, content, version=1, persistent=False)

    def _build_instructions_layer(self) -> PromptLayer:
        cache_key = f"inst_v{self._instructions_version}"
        cached = self._layer_cache.get(LayerType.INSTRUCTIONS)
        if cached and cached[0] == cache_key:
            return PromptLayer(LayerType.INSTRUCTIONS, cached[1], version=self._instructions_version, cache_key=cache_key)

        parts = []
        if self._tool_registry:
            tool_lines = []
            for t in self._tool_registry:
                name = t.get("name", "?")
                desc = t.get("description", "")[:120]
                tool_lines.append(f"- {name}: {desc}")
            parts.append(f"## Available Tools ({len(self._tool_registry)})\n" + "\n".join(tool_lines))

        if self._capability_list:
            parts.append(f"## Capabilities\n{', '.join(self._capability_list)}")

        content = "\n\n".join(parts) if parts else ""

        if content:
            self._layer_cache[LayerType.INSTRUCTIONS] = (cache_key, content)
        return PromptLayer(LayerType.INSTRUCTIONS, content, version=self._instructions_version, cache_key=cache_key, persistent=True)

    def _build_skills_index_layer(self) -> PromptLayer:
        cache_key = f"skills_v{hashlib.md5(str(self._skills_index).encode()).hexdigest()[:16]}"
        cached = self._layer_cache.get(LayerType.SKILLS_INDEX)
        if cached and cached[0] == cache_key:
            return PromptLayer(LayerType.SKILLS_INDEX, cached[1], version=1, cache_key=cache_key)

        if not self._skills_index:
            return PromptLayer(LayerType.SKILLS_INDEX, "", version=0, cache_key="", persistent=True)

        lines = [f"## Skills ({len(self._skills_index)})"]
        for s in self._skills_index:
            lines.append(f"- {s}")
        content = "\n".join(lines)
        self._layer_cache[LayerType.SKILLS_INDEX] = (cache_key, content)
        return PromptLayer(LayerType.SKILLS_INDEX, content, version=1, cache_key=cache_key, persistent=True)

    def _build_working_layer(
        self,
        user_message: str,
        context: Optional[list[dict]] = None,
        profile: Optional[dict] = None,
    ) -> PromptLayer:
        parts = [f"## Current Request\n{user_message}"]

        if profile:
            relevant = {k: v for k, v in profile.items() if k in ("name", "preferences", "goals")}
            if relevant:
                import json
                parts.append(f"## User Context\n{json.dumps(relevant, default=str)[:800]}")

        if context:
            recent = []
            for c in context[-8:]:
                role = c.get("role", "?")
                content = str(c.get("content", ""))[:300]
                recent.append(f"[{role}] {content}")
            if recent:
                parts.append(f"## Recent History ({len(recent)} messages)\n" + "\n".join(recent))

        content = "\n\n".join(parts)
        return PromptLayer(LayerType.WORKING, content, version=1, persistent=False)

    def assemble(
        self,
        user_message: str,
        user_name: str = "",
        session_id: str = "",
        context: Optional[list[dict]] = None,
        profile: Optional[dict] = None,
        layers: Optional[list[LayerType]] = None,
    ) -> PromptAssembly:
        layer_order = layers or [
            LayerType.SOUL,
            LayerType.MEMORY,
            LayerType.PROJECT,
            LayerType.SKILLS_INDEX,
            LayerType.INSTRUCTIONS,
            LayerType.METADATA,
            LayerType.WORKING,
        ]

        builder_map = {
            LayerType.SOUL: self._build_soul_layer,
            LayerType.MEMORY: self._build_memory_layer,
            LayerType.PROJECT: self._build_project_layer,
            LayerType.SKILLS_INDEX: self._build_skills_index_layer,
            LayerType.INSTRUCTIONS: self._build_instructions_layer,
            LayerType.METADATA: lambda: self._build_metadata_layer(user_name, session_id),
            LayerType.WORKING: lambda: self._build_working_layer(user_message, context, profile),
        }

        assembled = []
        for lt in layer_order:
            builder = builder_map.get(lt)
            if builder:
                layer = builder()
                if layer.content:
                    assembled.append(layer)

        self._build_count += 1
        result = PromptAssembly(assembled)
        logger.debug(f"Prompt assembled: {len(assembled)} layers, ~{result.token_estimate} tokens")
        return result

    @property
    def cache_stats(self) -> dict:
        return {
            "cached_layers": list(self._layer_cache.keys()),
            "build_count": self._build_count,
            "instructions_version": self._instructions_version,
        }

    def invalidate(self):
        self._layer_cache.clear()
        self._instructions_version += 1
