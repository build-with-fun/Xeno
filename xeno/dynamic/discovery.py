"""Dynamic agent discovery system.

Auto-discovers agents from:
- agents/ directory (each subfolder = one agent with description.md)
- media/ directory (media-specific agents like WhatsApp)
- Any custom directory configured via config
- Python modules that register themselves

Agent folder structure:
  agents/
    my_agent/
      description.md    <- frontmatter + description
      __init__.py       <- optional Python module
      tools/            <- optional agent-specific tools
      skills/           <- optional agent-specific skills

description.md format:
  ---
  name: my-agent
  model: deepseek:deepseek-chat
  tools: [shell, browser, code_exec]
  permissions: [read, write, execute]
  temperature: 0.7
  max_tokens: 4096
  tags: [research, coding]
  ---
  This agent does X, Y, Z.
  It specializes in ...
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentDescriptor:
    """Parsed description of a discovered agent."""
    id: str
    name: str
    description: str = ""
    folder_path: str = ""
    model: str = ""
    tools: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    subagents: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    tags: list[str] = field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    created_at: float = field(default_factory=time.time)
    last_modified: float = field(default_factory=time.time)
    # Always-on fields
    always_on: bool = False
    check_interval_minutes: int = 5
    restart_policy: str = "with_backoff"
    max_restarts: int = 10
    custom_tools_dir: str = "tools/"
    custom_tools: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "folder_path": self.folder_path, "model": self.model,
            "tools": self.tools, "permissions": self.permissions,
            "subagents": self.subagents, "temperature": self.temperature,
            "max_tokens": self.max_tokens, "tags": self.tags,
            "enabled": self.enabled, "metadata": self.metadata,
            "system_prompt": self.system_prompt[:200] + "..." if len(self.system_prompt) > 200 else self.system_prompt,
            "always_on": self.always_on,
            "check_interval_minutes": self.check_interval_minutes,
            "restart_policy": self.restart_policy,
            "max_restarts": self.max_restarts,
            "custom_tools_dir": self.custom_tools_dir,
            "custom_tools_count": len(self.custom_tools),
        }

    def get_full_prompt(self, base_prompt: str = "") -> str:
        """Generate the full system prompt for this agent."""
        if self.system_prompt:
            return self.system_prompt
        parts = [base_prompt] if base_prompt else []
        parts.append(f"You are {self.name}.")
        if self.description:
            parts.append(self.description)
        if self.tools:
            parts.append(f"You have access to these tools: {', '.join(self.tools)}.")
        return "\n\n".join(parts)

    def load_custom_tools(self) -> list[Any]:
        """Load custom tools from the agent's tools/ directory.

        Each Python file in tools/ should define tools using @tool decorator.
        Returns list of loaded tool functions.
        """
        if not self.folder_path:
            return []
        tools_dir = Path(self.folder_path) / self.custom_tools_dir
        if not tools_dir.exists():
            return []

        loaded = []
        for py_file in sorted(tools_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                module_name = f"xeno_agent_{self.id}_tool_{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)
                    # Find all @tool decorated functions or callable attributes
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if callable(attr) and hasattr(attr, "name"):
                            # It's a @tool decorated function
                            loaded.append(attr)
                            logger.info(f"Loaded custom tool '{attr_name}' from {py_file.name} for agent {self.id}")
                        elif callable(attr) and not attr_name.startswith("_") and attr_name not in ("os", "sys", "json", "time"):
                            # Check if it has a tool-like schema
                            if hasattr(attr, "args") or hasattr(attr, "InputType"):
                                loaded.append(attr)
                                logger.info(f"Loaded custom tool '{attr_name}' from {py_file.name} for agent {self.id}")
            except Exception as e:
                logger.error(f"Failed to load tools from {py_file}: {e}")

        self.custom_tools = loaded
        return loaded


def parse_description_md(file_path: Path) -> AgentDescriptor:
    """Parse a description.md file with YAML frontmatter."""
    content = file_path.read_text(encoding="utf-8")
    frontmatter = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_fm = parts[1].strip()
            body = parts[2].strip()
            for line in raw_fm.split("\n"):
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    # Parse lists: [a, b, c]
                    if val.startswith("[") and val.endswith("]"):
                        val = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
                    elif val.lower() in ("true", "yes"):
                        val = True
                    elif val.lower() in ("false", "no"):
                        val = False
                    elif val.replace(".", "").replace("-", "").isdigit():
                        try:
                            val = float(val) if "." in val else int(val)
                        except ValueError:
                            pass
                    frontmatter[key] = val

    # Derive agent ID from folder name
    folder_name = file_path.parent.name
    agent_id = frontmatter.get("id", frontmatter.get("name", folder_name))
    name = frontmatter.get("name", folder_name.replace("_", " ").replace("-", " ").title())

    return AgentDescriptor(
        id=str(agent_id),
        name=str(name),
        description=body,
        folder_path=str(file_path.parent),
        model=str(frontmatter.get("model", "")),
        tools=frontmatter.get("tools", []) if isinstance(frontmatter.get("tools"), list) else [],
        permissions=frontmatter.get("permissions", []) if isinstance(frontmatter.get("permissions"), list) else [],
        subagents=frontmatter.get("subagents", []) if isinstance(frontmatter.get("subagents"), list) else [],
        temperature=float(frontmatter.get("temperature", 0.7)),
        max_tokens=int(frontmatter.get("max_tokens", 4096)),
        tags=frontmatter.get("tags", []) if isinstance(frontmatter.get("tags"), list) else [],
        enabled=frontmatter.get("enabled", True) if isinstance(frontmatter.get("enabled", True), bool) else True,
        system_prompt=body,
        metadata=frontmatter.get("metadata", {}) if isinstance(frontmatter.get("metadata", {}), dict) else {},
        always_on=frontmatter.get("always_on", False) if isinstance(frontmatter.get("always_on", False), bool) else False,
        check_interval_minutes=int(frontmatter.get("check_interval_minutes", 5)),
        restart_policy=str(frontmatter.get("restart_policy", "with_backoff")),
        max_restarts=int(frontmatter.get("max_restarts", 10)),
        custom_tools_dir=str(frontmatter.get("custom_tools_dir", "tools/")),
    )


class AgentDiscovery:
    """Discovers and manages agents from the filesystem.

    Scans configured directories for agent folders containing description.md.
    Supports hot-reload via file watching.
    """

    def __init__(self, scan_dirs: Optional[list[str]] = None):
        self.scan_dirs = scan_dirs or []
        self.agents: dict[str, AgentDescriptor] = {}
        self._module_cache: dict[str, Any] = {}
        self._file_mtimes: dict[str, float] = {}

    def add_scan_dir(self, directory: str) -> None:
        """Add a directory to scan for agents."""
        if directory not in self.scan_dirs:
            self.scan_dirs.append(directory)

    def scan(self) -> list[AgentDescriptor]:
        """Scan all directories and discover agents."""
        discovered = []
        for scan_dir in self.scan_dirs:
            dir_path = Path(scan_dir)
            if not dir_path.exists():
                continue
            for entry in sorted(dir_path.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith((".", "_")):
                    continue
                desc_file = entry / "description.md"
                if desc_file.exists():
                    try:
                        descriptor = parse_description_md(desc_file)
                        self.agents[descriptor.id] = descriptor
                        self._file_mtimes[str(desc_file)] = desc_file.stat().st_mtime
                        discovered.append(descriptor)
                        logger.info(f"Discovered agent: {descriptor.name} ({descriptor.id})")
                    except Exception as e:
                        logger.error(f"Failed to parse agent at {entry}: {e}")
                # Also check for __init__.py based agents
                init_file = entry / "__init__.py"
                if init_file.exists() and str(entry) not in [d.folder_path for d in self.agents.values()]:
                    try:
                        descriptor = self._load_module_agent(entry)
                        if descriptor:
                            self.agents[descriptor.id] = descriptor
                            discovered.append(descriptor)
                    except Exception as e:
                        logger.error(f"Failed to load module agent at {entry}: {e}")
        return discovered

    def _load_module_agent(self, folder: Path) -> Optional[AgentDescriptor]:
        """Load an agent from a Python module (no description.md)."""
        module_name = f"xeno_agent_{folder.name}"
        init_path = folder / "__init__.py"
        if not init_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(init_path))
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            # Look for agent descriptor or create one from module attrs
            if hasattr(module, "AGENT_DESCRIPTOR"):
                return module.AGENT_DESCRIPTOR
            if hasattr(module, "get_agent_descriptor"):
                return module.get_agent_descriptor()
            # Auto-create from module name
            return AgentDescriptor(
                id=folder.name,
                name=folder.name.replace("_", " ").replace("-", " ").title(),
                description=getattr(module, "__doc__", "") or f"Agent from {folder.name}",
                folder_path=str(folder),
            )
        except Exception as e:
            logger.error(f"Error loading module agent {folder}: {e}")
            return None

    def get_agent(self, agent_id: str) -> Optional[AgentDescriptor]:
        return self.agents.get(agent_id)

    def list_agents(self, enabled_only: bool = True) -> list[AgentDescriptor]:
        agents = list(self.agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents

    def get_agents_by_tag(self, tag: str) -> list[AgentDescriptor]:
        return [a for a in self.agents.values() if tag in a.tags and a.enabled]

    def register_agent(self, descriptor: AgentDescriptor) -> None:
        """Manually register an agent."""
        self.agents[descriptor.id] = descriptor

    def unregister_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False

    def check_for_updates(self) -> list[str]:
        """Check if any description.md files have changed. Returns list of changed agent IDs."""
        changed = []
        for agent in self.agents.values():
            desc_file = Path(agent.folder_path) / "description.md"
            if desc_file.exists():
                current_mtime = desc_file.stat().st_mtime
                old_mtime = self._file_mtimes.get(str(desc_file), 0)
                if current_mtime > old_mtime:
                    changed.append(agent.id)
                    self._file_mtimes[str(desc_file)] = current_mtime
        return changed

    def reload_agent(self, agent_id: str) -> Optional[AgentDescriptor]:
        """Reload a single agent from disk."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        desc_file = Path(agent.folder_path) / "description.md"
        if desc_file.exists():
            try:
                descriptor = parse_description_md(desc_file)
                self.agents[descriptor.id] = descriptor
                return descriptor
            except Exception as e:
                logger.error(f"Failed to reload agent {agent_id}: {e}")
        return agent

    def get_agent_tools(self, agent_id: str) -> list[str]:
        """Get the tool list for a specific agent."""
        agent = self.agents.get(agent_id)
        if agent:
            return agent.tools
        return []

    def summary(self) -> str:
        enabled = sum(1 for a in self.agents.values() if a.enabled)
        return f"Agent Discovery: {enabled}/{len(self.agents)} agents enabled across {len(self.scan_dirs)} dirs"
