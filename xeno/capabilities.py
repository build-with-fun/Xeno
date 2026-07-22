"""Capability system — detects gaps and scaffolds new abilities.

The agent can:
1. Detect what it can't do (gap analysis)
2. Scaffold new tools, skills, and MCP servers to fill gaps
3. Test capabilities before deploying them
4. Auto-extend itself when it encounters unknown tasks
5. Learn from successful capability creation

This is the "give itself new abilities" engine.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class CapabilityGap:
    id: str
    description: str
    gap_type: str  # tool, skill, mcp, knowledge
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""
    resolution_type: str = ""  # tool_created, skill_created, mcp_added, knowledge_added

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description[:200],
            "gap_type": self.gap_type, "detected": self.detected_at,
            "resolved": self.resolved, "resolution": self.resolution,
            "resolution_type": self.resolution_type,
        }


@dataclass
class ScaffoldedCapability:
    id: str
    name: str
    capability_type: str  # tool, skill, mcp
    code: str = ""
    config: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    tested: bool = False
    test_passed: bool = False
    deployed: bool = False
    gap_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "type": self.capability_type, "created": self.created_at,
            "tested": self.tested, "test_passed": self.test_passed,
            "deployed": self.deployed, "gap_id": self.gap_id,
        }


# --- Capability keyword detection ---

CAPABILITY_KEYWORDS = {
    "tool": [
        "need a tool", "missing tool", "don't have a tool", "can't do this",
        "need ability", "can't access", "unable to", "missing capability",
    ],
    "skill": [
        "need a skill", "missing skill", "don't know how", "need workflow",
        "need procedure", "need steps for", "create a workflow",
    ],
    "mcp": [
        "need mcp", "missing mcp", "external server", "third party",
        "api integration", "connect to", "need integration",
    ],
    "knowledge": [
        "don't know", "no information", "can't find", "missing data",
        "no knowledge about", "need to learn",
    ],
}


class CapabilityManager:
    """Detects capability gaps and scaffolds new abilities.

    On every interaction, this system:
    - Scans the request for capability gaps
    - Determines what type of capability is needed
    - Scaffolds tools, skills, or MCP servers
    - Tests them before deployment
    - Auto-deploys on success
    - Learns from the process
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/capabilities")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.gaps: list[CapabilityGap] = []
        self.scaffolded: list[ScaffoldedCapability] = []
        self._load()

    # --- Gap Detection ---

    def detect_gaps(self, user_input: str, error_context: str = "", available_tools: list[str] = None) -> list[CapabilityGap]:
        """Analyze input + error for capability gaps."""
        gaps = []
        text = f"{user_input} {error_context}".lower()
        available = set(t.lower() for t in (available_tools or []))

        # Check for explicit capability requests
        for gap_type, keywords in CAPABILITY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    gap = CapabilityGap(
                        id=f"gap_{uuid.uuid4().hex[:8]}",
                        description=user_input[:200],
                        gap_type=gap_type,
                    )
                    gaps.append(gap)
                    break

        # Check for tool-matching gaps (user asks for something no tool handles)
        if not gaps and available_tools:
            action_verbs = ["search", "create", "delete", "update", "find", "list",
                          "install", "run", "execute", "send", "fetch", "download"]
            for verb in action_verbs:
                if text.startswith(verb) or f" {verb} " in text:
                    # Check if any tool handles this
                    handled = any(verb in t for t in available)
                    if not handled:
                        gap = CapabilityGap(
                            id=f"gap_{uuid.uuid4().hex[:8]}",
                            description=f"Need capability for: {verb} based on '{user_input[:100]}'",
                            gap_type="tool",
                        )
                        gaps.append(gap)
                        break

        for g in gaps:
            self.gaps.append(g)
        self._save()
        return gaps

    def mark_gap_resolved(self, gap_id: str, resolution: str, resolution_type: str) -> bool:
        for g in self.gaps:
            if g.id == gap_id:
                g.resolved = True
                g.resolution = resolution
                g.resolution_type = resolution_type
                self._save()
                return True
        return False

    # --- Scaffolding ---

    def scaffold_tool(self, name: str, description: str, code: str, gap_id: str = "") -> ScaffoldedCapability:
        """Create a new tool from Python code."""
        # Validate the code is syntactically correct
        try:
            compile(code, f"<{name}>", "exec")
        except SyntaxError as e:
            raise ValueError(f"Tool code has syntax error: {e}")

        cap = ScaffoldedCapability(
            id=f"cap_{uuid.uuid4().hex[:8]}",
            name=name,
            capability_type="tool",
            code=code,
            gap_id=gap_id,
        )
        self.scaffolded.append(cap)
        self._save()
        return cap

    def scaffold_skill(self, name: str, description: str, body: str, gap_id: str = "") -> ScaffoldedCapability:
        """Create a new skill (SKILL.md content)."""
        skill_content = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}"
        cap = ScaffoldedCapability(
            id=f"cap_{uuid.uuid4().hex[:8]}",
            name=name,
            capability_type="skill",
            code=skill_content,
            gap_id=gap_id,
        )
        self.scaffolded.append(cap)
        self._save()
        return cap

    def scaffold_mcp(self, name: str, config: dict, gap_id: str = "") -> ScaffoldedCapability:
        """Create a new MCP server configuration."""
        cap = ScaffoldedCapability(
            id=f"cap_{uuid.uuid4().hex[:8]}",
            name=name,
            capability_type="mcp",
            config=config,
            gap_id=gap_id,
        )
        self.scaffolded.append(cap)
        self._save()
        return cap

    # --- Testing ---

    def test_tool(self, cap_id: str, test_input: str = "") -> bool:
        """Test a scaffolded tool by executing it."""
        cap = self._get_cap(cap_id)
        if not cap or cap.capability_type != "tool":
            return False

        try:
            namespace: dict[str, Any] = {}
            exec(cap.code, namespace)
            # Find the tool function (the one that's not underscore-prefixed)
            tool_funcs = {k: v for k, v in namespace.items()
                         if callable(v) and not k.startswith("_")}
            if not tool_funcs:
                return False
            # Try calling the first function
            func_name, func = next(iter(tool_funcs.items()))
            if test_input:
                result = func(test_input)
            else:
                result = func()
            cap.tested = True
            cap.test_passed = True
            self._save()
            return True
        except Exception as e:
            cap.tested = True
            cap.test_passed = False
            self._save()
            return False

    # --- Deployment ---

    def deploy_tool(self, cap_id: str) -> Optional[str]:
        """Deploy a scaffolded tool into the live tool registry."""
        cap = self._get_cap(cap_id)
        if not cap or cap.capability_type != "tool":
            return None

        try:
            namespace: dict[str, Any] = {}
            exec(cap.code, namespace)
            tool_funcs = {k: v for k, v in namespace.items()
                         if callable(v) and not k.startswith("_")}
            if not tool_funcs:
                return None

            # Register the tool
            from xeno.tool_registry import ToolRegistry
            from xeno.config import XenoConfig
            config = XenoConfig.from_env()
            registry = ToolRegistry(config.data_dir / "tools")

            func_name, func = next(iter(tool_funcs.items()))
            registry.register(func, name=cap.name)

            cap.deployed = True
            self._save()
            return cap.name
        except Exception as e:
            return None

    def deploy_skill(self, cap_id: str) -> Optional[str]:
        """Deploy a scaffolded skill into the skills directory."""
        cap = self._get_cap(cap_id)
        if not cap or cap.capability_type != "skill":
            return None

        from xeno.skills_manager import SkillManager
        from xeno.config import XenoConfig
        config = XenoConfig.from_env()
        sm = SkillManager(config)

        # Parse skill content
        content = cap.code
        name = cap.name
        desc = ""
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                header = parts[1].strip()
                body = parts[2].strip()
                for line in header.split("\n"):
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()

        result = sm.create(name, desc, body)
        cap.deployed = True
        self._save()
        return result

    # --- Auto-extend (full pipeline) ---

    def auto_extend(self, description: str, available_tools: list[str] = None) -> dict[str, Any]:
        """Full pipeline: detect gap → scaffold → test → deploy.

        Returns what was done.
        """
        result: dict[str, Any] = {
            "gap_detected": False, "gap_type": "",
            "scaffolded": False, "tested": False, "deployed": False,
            "details": [],
        }

        # 1. Detect gap
        gaps = self.detect_gaps(description, available_tools=available_tools)
        if not gaps:
            result["details"].append("No capability gap detected")
            return result

        gap = gaps[0]
        result["gap_detected"] = True
        result["gap_type"] = gap.gap_type

        # 2. Scaffold based on gap type
        if gap.gap_type == "tool":
            tool_name = re.sub(r'[^a-z0-9_]', '_', description.lower()[:40]).strip('_')
            code = self._generate_tool_code(tool_name, description)
            cap = self.scaffold_tool(tool_name, description, code, gap_id=gap.id)
            result["scaffolded"] = True
            result["details"].append(f"Created tool scaffold: {tool_name}")

            # 3. Test
            if self.test_tool(cap.id):
                result["tested"] = True
                result["details"].append("Tool test passed")

                # 4. Deploy
                deployed = self.deploy_tool(cap.id)
                if deployed:
                    result["deployed"] = True
                    result["details"].append(f"Tool deployed: {deployed}")
                    self.mark_gap_resolved(gap.id, f"Tool created: {deployed}", "tool_created")

        elif gap.gap_type == "skill":
            skill_name = re.sub(r'[^a-z0-9_]', '_', description.lower()[:40]).strip('_')
            body = self._generate_skill_body(skill_name, description)
            cap = self.scaffold_skill(skill_name, description, body, gap_id=gap.id)
            result["scaffolded"] = True

            deployed = self.deploy_skill(cap.id)
            if deployed:
                result["deployed"] = True
                result["details"].append(f"Skill deployed: {skill_name}")
                self.mark_gap_resolved(gap.id, f"Skill created: {skill_name}", "skill_created")

        elif gap.gap_type == "mcp":
            mcp_name = re.sub(r'[^a-z0-9_]', '_', description.lower()[:40]).strip('_')
            config = {"type": "remote", "url": "", "enabled": True}
            cap = self.scaffold_mcp(mcp_name, config, gap_id=gap.id)
            result["scaffolded"] = True
            result["details"].append(f"MCP scaffold created: {mcp_name} (needs URL config)")

        return result

    # --- Code generation ---

    def _generate_tool_code(self, name: str, description: str) -> str:
        """Generate a basic tool Python file from a description."""
        func_name = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return f'''"""Auto-scaffolded tool: {description}"""

from __future__ import annotations


def {func_name}(input_text: str = "") -> str:
    """{description}

    Args:
        input_text: The input to process.

    Returns:
        Result of processing.
    """
    # TODO: Implement the actual logic for this tool
    # This was auto-generated as a scaffold.
    # Replace this body with the real implementation.
    return f"Tool '{name}' executed with input: {{input_text}} (scaffold — needs implementation)"


def register(registry):
    """Register this tool with the tool registry."""
    registry.register({func_name}, name="{name}")
'''

    def _generate_skill_body(self, name: str, description: str) -> str:
        """Generate SKILL.md body from a description."""
        return f"""# {name}

## Purpose
{description}

## Steps
1. Understand the task requirements
2. Break down into subtasks
3. Execute each subtask
4. Verify the results
5. Report completion

## Notes
- This skill was auto-generated as a scaffold
- Customize the steps based on actual requirements
- Add examples for common use cases
"""

    # --- Summary & getters ---

    def get_active_gaps(self, limit: int = 20) -> list[CapabilityGap]:
        return [g for g in self.gaps if not g.resolved][:limit]

    def get_scaffolded(self, capability_type: str = "", limit: int = 20) -> list[ScaffoldedCapability]:
        caps = self.scaffolded
        if capability_type:
            caps = [c for c in caps if c.capability_type == capability_type]
        return caps[-limit:]

    def summary(self) -> str:
        unresolved = sum(1 for g in self.gaps if not g.resolved)
        deployed = sum(1 for c in self.scaffolded if c.deployed)
        return (
            f"Capabilities: {len(self.gaps)} gaps detected ({unresolved} unresolved), "
            f"{len(self.scaffolded)} scaffolded ({deployed} deployed)"
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_gaps": len(self.gaps),
            "unresolved_gaps": sum(1 for g in self.gaps if not g.resolved),
            "total_scaffolded": len(self.scaffolded),
            "deployed": sum(1 for c in self.scaffolded if c.deployed),
            "by_type": {
                "tool": sum(1 for c in self.scaffolded if c.capability_type == "tool"),
                "skill": sum(1 for c in self.scaffolded if c.capability_type == "skill"),
                "mcp": sum(1 for c in self.scaffolded if c.capability_type == "mcp"),
            },
        }

    # --- Helpers ---

    def _get_cap(self, cap_id: str) -> Optional[ScaffoldedCapability]:
        for c in self.scaffolded:
            if c.id == cap_id:
                return c
        return None

    # --- Persistence ---

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "gaps.json").write_text(
            json.dumps([g.to_dict() for g in self.gaps[-500:]], indent=2)
        )
        (self.data_dir / "scaffolded.json").write_text(
            json.dumps([c.to_dict() for c in self.scaffolded[-200:]], indent=2)
        )

    def _load(self) -> None:
        for name, cls, target in [
            ("gaps.json", CapabilityGap, "gaps"),
            ("scaffolded.json", ScaffoldedCapability, "scaffolded"),
        ]:
            path = self.data_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    setattr(self, target, [
                        cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
                        for d in data
                    ])
                except Exception:
                    pass
