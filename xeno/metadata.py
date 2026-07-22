"""Unified metadata schema for skills, plugins, and MCP servers.

Provides a common capability model so the agent can intelligently pick
the best component for any task. Every component type (skill, plugin,
MCP server) shares the same metadata fields:

  - tags:         semantic keywords for matching
  - category:     domain classification
  - capabilities: what the component can do (high-level)
  - dependencies: required packages, env vars, or other components
  - when_to_use:  hints for the agent about when to activate this component
  - examples:     sample inputs/outputs for few-shot matching
  - priority:     tie-breaking order when multiple components match
  - cost:         relative cost tier (free / low / medium / high)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ComponentMetadata:
    """Unified metadata for any discoverable component."""
    name: str
    component_type: str  # "skill" | "plugin" | "mcp"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = ""  # coding, automation, research, memory, devops, etc.
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    when_to_use: str = ""
    examples: list[dict[str, str]] = field(default_factory=list)
    priority: int = 50  # 0=highest, 100=lowest
    cost: str = "free"  # free, low, medium, high
    version: str = "0.0.1"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "component_type": self.component_type,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "when_to_use": self.when_to_use,
            "examples": self.examples,
            "priority": self.priority,
            "cost": self.cost,
            "version": self.version,
            "enabled": self.enabled,
        }

    def matches_query(self, query: str) -> float:
        """Score how well this component matches a natural language query.
        Returns 0.0-1.0 (higher = better match)."""
        query_lower = query.lower()
        score = 0.0

        # Tag matching (strong signal)
        for tag in self.tags:
            if tag.lower() in query_lower:
                score += 0.3
            elif any(w in query_lower for w in tag.lower().split()):
                score += 0.1

        # Category matching
        if self.category and self.category.lower() in query_lower:
            score += 0.2

        # Capability matching
        for cap in self.capabilities:
            cap_words = cap.lower().split()
            matches = sum(1 for w in cap_words if w in query_lower)
            if matches > 0:
                score += 0.15 * (matches / len(cap_words))

        # when_to_use keyword matching
        if self.when_to_use:
            hint_words = set(self.when_to_use.lower().split())
            query_words = set(query_lower.split())
            overlap = hint_words & query_words
            if overlap:
                score += 0.1 * min(len(overlap) / 3, 1.0)

        # Description keyword matching (weak signal)
        if self.description:
            desc_words = set(re.findall(r'\w{3,}', self.description.lower()))
            query_words = set(re.findall(r'\w{3,}', query_lower))
            overlap = desc_words & query_words
            if overlap:
                score += 0.05 * min(len(overlap) / 5, 1.0)

        # Priority bonus (lower priority number = higher bonus)
        score += (100 - self.priority) / 1000

        return min(score, 1.0)


class CapabilityIndex:
    """Index of all components for fast capability-based lookup."""

    def __init__(self):
        self.components: dict[str, ComponentMetadata] = {}

    def register(self, meta: ComponentMetadata) -> None:
        key = f"{meta.component_type}:{meta.name}"
        self.components[key] = meta

    def unregister(self, component_type: str, name: str) -> None:
        key = f"{component_type}:{name}"
        self.components.pop(key, None)

    def search(self, query: str, top_k: int = 5, component_type: str | None = None) -> list[ComponentMetadata]:
        """Find the best matching components for a query."""
        candidates = self.components.values()
        if component_type:
            candidates = [c for c in candidates if c.component_type == component_type]

        scored = [(c, c.matches_query(query)) for c in candidates if c.enabled]
        scored.sort(key=lambda x: (-x[1], x[0].priority))
        return [c for c, s in scored[:top_k] if s > 0.05]

    def by_category(self, category: str) -> list[ComponentMetadata]:
        return [c for c in self.components.values() if c.category == category and c.enabled]

    def by_tag(self, tag: str) -> list[ComponentMetadata]:
        return [c for c in self.components.values() if tag in c.tags and c.enabled]

    def summary(self) -> str:
        by_type: dict[str, int] = {}
        for c in self.components.values():
            by_type[c.component_type] = by_type.get(c.component_type, 0) + 1
        parts = [f"{t}: {n}" for t, n in sorted(by_type.items())]
        return f"CapabilityIndex: {', '.join(parts)} ({len(self.components)} total)"

    def export_catalog(self) -> str:
        """Export a human-readable catalog the agent can use for tool selection."""
        lines = ["# Component Catalog\n"]
        by_cat: dict[str, list[ComponentMetadata]] = {}
        for c in self.components.values():
            if c.enabled:
                cat = c.category or "uncategorized"
                by_cat.setdefault(cat, []).append(c)

        for cat, comps in sorted(by_cat.items()):
            lines.append(f"\n## {cat.title()}")
            for c in sorted(comps, key=lambda x: x.priority):
                tags_str = ", ".join(c.tags[:5]) if c.tags else ""
                caps_str = "; ".join(c.capabilities[:3]) if c.capabilities else ""
                lines.append(f"- **{c.name}** ({c.component_type}) — {c.description[:80]}")
                if tags_str:
                    lines.append(f"  Tags: {tags_str}")
                if caps_str:
                    lines.append(f"  Capabilities: {caps_str}")
                if c.when_to_use:
                    lines.append(f"  When to use: {c.when_to_use[:100]}")

        return "\n".join(lines)


def parse_skill_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML-like frontmatter from SKILL.md content.
    Handles simple key: value pairs, plus key: [list] inline syntax."""
    meta = {}
    if not content.startswith("---"):
        return meta
    parts = content.split("---", 2)
    if len(parts) < 3:
        return meta
    for line in parts[1].strip().split("\n"):
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        # Parse lists: [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if inner:
                meta[key] = [item.strip().strip('"').strip("'") for item in inner.split(",")]
            else:
                meta[key] = []
        elif val.lower() in ("true", "false"):
            meta[key] = val.lower() == "true"
        else:
            meta[key] = val.strip('"').strip("'")
    return meta


def load_mcp_metadata(server_dir: Path) -> ComponentMetadata | None:
    """Load metadata.json from an MCP server directory."""
    meta_file = server_dir / "metadata.json"
    if not meta_file.exists():
        return None
    try:
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        return ComponentMetadata(
            name=data.get("name", server_dir.name),
            component_type="mcp",
            description=data.get("description", ""),
            tags=data.get("tags", []),
            category=data.get("category", ""),
            capabilities=data.get("capabilities", []),
            dependencies=data.get("dependencies", []),
            when_to_use=data.get("when_to_use", ""),
            examples=data.get("examples", []),
            priority=data.get("priority", 50),
            cost=data.get("cost", "free"),
            version=data.get("version", "0.0.1"),
            enabled=data.get("enabled", True),
        )
    except Exception:
        return None


def build_skill_metadata(name: str, frontmatter: dict[str, Any]) -> ComponentMetadata:
    """Build ComponentMetadata from parsed skill frontmatter."""
    return ComponentMetadata(
        name=name,
        component_type="skill",
        description=frontmatter.get("description", ""),
        tags=frontmatter.get("tags", []) if isinstance(frontmatter.get("tags"), list) else [],
        category=frontmatter.get("category", ""),
        capabilities=frontmatter.get("capabilities", []) if isinstance(frontmatter.get("capabilities"), list) else [],
        dependencies=frontmatter.get("dependencies", []) if isinstance(frontmatter.get("dependencies"), list) else [],
        when_to_use=frontmatter.get("when_to_use", ""),
        examples=frontmatter.get("examples", []) if isinstance(frontmatter.get("examples"), list) else [],
        priority=int(frontmatter.get("priority", 50)),
        cost=frontmatter.get("cost", "free"),
        version=frontmatter.get("version", "0.0.1"),
        enabled=frontmatter.get("enabled", True) if isinstance(frontmatter.get("enabled", True), bool) else True,
    )


def build_plugin_metadata(name: str, plugin_data: dict[str, Any]) -> ComponentMetadata:
    """Build ComponentMetadata from plugin.json data."""
    return ComponentMetadata(
        name=name,
        component_type="plugin",
        description=plugin_data.get("description", ""),
        tags=plugin_data.get("tags", []),
        category=plugin_data.get("category", ""),
        capabilities=plugin_data.get("capabilities", []),
        dependencies=plugin_data.get("dependencies", []),
        when_to_use=plugin_data.get("when_to_use", ""),
        examples=plugin_data.get("examples", []),
        priority=int(plugin_data.get("priority", 50)),
        cost=plugin_data.get("cost", "free"),
        version=plugin_data.get("version", "0.0.1"),
        enabled=plugin_data.get("enabled", True),
    )
