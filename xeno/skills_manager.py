"""Skills manager — full CRUD for SKILL.md files.

The agent uses this to create, list, search, load, update, and delete skills.
Skills are markdown files with YAML frontmatter stored in the skills/ directory.
The agent creates skills from patterns it learns, from user instructions,
and from error prevention. Nothing is hardcoded — the agent decides what to create.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SkillManager:
    """Manage SKILL.md files — create, read, update, delete, search."""

    def __init__(self, config=None, skills_dir: Optional[Path] = None):
        if skills_dir:
            self.skills_dir = skills_dir
        elif config and hasattr(config, "data_dir"):
            self.skills_dir = config.data_dir.parent / "skills"
        else:
            self.skills_dir = Path("skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}
        self.capability_index = None
        self._rebuild_index()

    def discover(self) -> list[dict]:
        """Discover all skills and build capability index. Returns list of skill metadata."""
        self._rebuild_index()
        try:
            from xeno.metadata import CapabilityIndex, ComponentMetadata
            self.capability_index = CapabilityIndex()
            for name, info in self._index.items():
                meta = info["meta"]
                comp = ComponentMetadata(
                    name=name,
                    component_type="skill",
                    description=meta.get("description", ""),
                    capabilities=meta.get("capabilities", []),
                    tags=meta.get("tags", []),
                    when_to_use=meta.get("when_to_use", ""),
                )
                self.capability_index.register(comp)
        except Exception:
            self.capability_index = None
        return list(self._index.values())

    def _rebuild_index(self):
        """Scan all SKILL.md files and build an index."""
        self._index.clear()
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    meta = self._parse_frontmatter(skill_file)
                    if meta:
                        self._index[meta.get("name", skill_dir.name)] = {
                            "path": skill_file,
                            "dir": skill_dir,
                            "meta": meta,
                        }

    def _parse_frontmatter(self, path: Path) -> Optional[dict]:
        """Extract YAML frontmatter from a SKILL.md file."""
        try:
            content = path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return None
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None
            # Simple YAML parsing (no external dependency)
            meta = {}
            for line in parts[1].strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()
                    if value.startswith("[") and value.endswith("]"):
                        # Parse array
                        inner = value[1:-1].strip()
                        if inner:
                            meta[key] = [v.strip().strip("\"'") for v in inner.split(",")]
                        else:
                            meta[key] = []
                    elif value.lower() in ("true", "false"):
                        meta[key] = value.lower() == "true"
                    elif value.isdigit():
                        meta[key] = int(value)
                    else:
                        meta[key] = value.strip("\"'")
            return meta
        except Exception as e:
            logger.debug(f"Failed to parse frontmatter from {path}: {e}")
            return None

    def list_skills(self) -> list[dict]:
        """List all available skills with their metadata."""
        result = []
        for name, info in self._index.items():
            meta = info["meta"].copy()
            meta["path"] = str(info["path"])
            result.append(meta)
        return sorted(result, key=lambda x: x.get("priority", 0), reverse=True)

    def get_skill(self, name: str) -> Optional[dict]:
        """Get a skill by name — returns full content + metadata."""
        info = self._index.get(name)
        if not info:
            return None
        try:
            content = info["path"].read_text(encoding="utf-8")
            parts = content.split("---", 2)
            body = parts[2].strip() if len(parts) >= 3 else content
            return {
                "name": name,
                "meta": info["meta"],
                "content": body,
                "path": str(info["path"]),
            }
        except Exception as e:
            logger.error(f"Failed to read skill {name}: {e}")
            return None

    def search_skills(self, query: str, top_k: int = 5) -> list[dict]:
        """Search skills by description, tags, and capabilities using keyword overlap."""
        query_words = set(query.lower().split())
        scored = []
        for name, info in self._index.items():
            meta = info["meta"]
            searchable = " ".join([
                meta.get("name", ""),
                meta.get("description", ""),
                meta.get("when_to_use", ""),
                " ".join(meta.get("tags", [])),
                " ".join(meta.get("capabilities", [])),
            ]).lower()
            search_words = set(searchable.split())
            overlap = len(query_words & search_words)
            if overlap > 0:
                scored.append((overlap, name, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"name": name, "score": score, **meta} for score, name, meta in scored[:top_k]]

    def create_skill(
        self,
        name: str,
        description: str,
        body: str,
        tags: Optional[list[str]] = None,
        category: str = "general",
        capabilities: Optional[list[str]] = None,
        when_to_use: str = "",
        priority: int = 30,
        cost: str = "free",
    ) -> str:
        """Create a new skill with SKILL.md file. Returns the path."""
        # Sanitize name for directory
        safe_name = re.sub(r"[^a-z0-9_\-]", "_", name.lower().strip())[:40]
        skill_dir = self.skills_dir / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists():
            return f"Skill '{safe_name}' already exists at {skill_file}"

        # Build frontmatter
        tags_str = ", ".join(tags) if tags else ""
        caps_str = ", ".join(capabilities) if capabilities else ""

        frontmatter = f"""---
name: {safe_name}
description: {description}
tags: [{tags_str}]
category: {category}
capabilities: [{caps_str}]
when_to_use: {when_to_use}
priority: {priority}
cost: {cost}
version: 0.0.1
enabled: true
created_at: {time.strftime("%Y-%m-%dT%H:%M:%S")}
auto_created: true
---"""

        content = f"{frontmatter}\n\n# {name}\n\n{body}\n"
        skill_file.write_text(content, encoding="utf-8")

        # Rebuild index
        self._rebuild_index()
        logger.info(f"Created skill: {safe_name} at {skill_file}")
        return f"Skill '{safe_name}' created at {skill_file}"

    def update_skill(self, name: str, body: str = "", description: str = "", tags: Optional[list[str]] = None) -> str:
        """Update an existing skill's body or metadata."""
        info = self._index.get(name)
        if not info:
            return f"Skill '{name}' not found"

        skill_file = info["path"]
        try:
            content = skill_file.read_text(encoding="utf-8")
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                # Update specific fields in frontmatter
                if description:
                    frontmatter = re.sub(
                        r"description:.*$", f"description: {description}",
                        frontmatter, flags=re.MULTILINE,
                    )
                if tags:
                    tags_str = ", ".join(tags)
                    frontmatter = re.sub(
                        r"tags:.*$", f"tags: [{tags_str}]",
                        frontmatter, flags=re.MULTILINE,
                    )
                if body:
                    new_content = f"---{frontmatter}---\n\n# {name}\n\n{body}\n"
                else:
                    new_content = f"---{frontmatter}---{parts[2]}"
                skill_file.write_text(new_content, encoding="utf-8")
                self._rebuild_index()
                return f"Skill '{name}' updated"
            return f"Failed to parse skill '{name}'"
        except Exception as e:
            return f"Error updating skill '{name}': {e}"

    def delete_skill(self, name: str) -> str:
        """Delete a skill and its directory."""
        info = self._index.get(name)
        if not info:
            return f"Skill '{name}' not found"
        try:
            import shutil
            shutil.rmtree(info["dir"])
            self._rebuild_index()
            return f"Skill '{name}' deleted"
        except Exception as e:
            return f"Error deleting skill '{name}': {e}"

    def create_from_pattern(
        self,
        name: str,
        description: str,
        pattern_type: str,
        trigger: str,
        solution: str,
        steps: Optional[list[str]] = None,
    ) -> str:
        """Create a skill from an observed pattern (error pattern, success pattern, user request)."""
        body = f"""## Purpose
This skill was auto-generated from a {pattern_type} pattern.

## Trigger
{trigger}

## Solution
{solution}

## Steps
"""
        if steps:
            for i, step in enumerate(steps, 1):
                body += f"{i}. {step}\n"
        else:
            body += "1. Identify the situation matching the trigger\n2. Apply the solution above\n3. Verify the result\n"

        body += f"""
## Notes
- Auto-generated from observed {pattern_type} pattern
- The agent learned this from experience
- Review and refine as needed
"""
        return self.create_skill(
            name=name,
            description=description,
            body=body,
            tags=[pattern_type, "auto_generated", "learned"],
            category="learned",
            when_to_use=f"Use when: {trigger}",
            priority=40,
        )

    def count(self) -> int:
        return len(self._index)

    def summary(self) -> str:
        skills = self.list_skills()
        return f"Skills: {len(skills)} total — {', '.join(s['name'] for s in skills[:10])}"

    # --- Backward-compatible aliases (used by metatools, self_heal, capabilities) ---

    def create(self, name: str, description: str, body: str) -> str:
        return self.create_skill(name, description, body)

    def list_all(self) -> list[dict]:
        return self.list_skills()

    def load(self, name: str) -> Optional[dict]:
        return self.get_skill(name)

    def delete(self, name: str) -> str:
        return self.delete_skill(name)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        return self.search_skills(query, top_k)


# ============================================================================
# Singleton getter
# ============================================================================

_skills_manager_instance = None


def get_skills_manager():
    """Get or create the global skills manager singleton."""
    global _skills_manager_instance
    if _skills_manager_instance is None:
        try:
            _skills_manager_instance = SkillManager()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to create skills manager: {e}")
            return None
    return _skills_manager_instance
