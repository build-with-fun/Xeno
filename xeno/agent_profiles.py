"""Agent profiles and persona management.

Implements:
- Configurable agent personalities and personas
- Tone and style settings
- Capability profiles (what each agent can do)
- Behavioral modifiers
- Profile-based prompt generation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Personality:
    tone: str = "professional"  # professional, casual, friendly, formal, technical
    verbosity: str = "concise"  # concise, moderate, verbose
    style: str = "direct"  # direct, Socratic, collaborative, instructional
    humor: bool = False
    empathy: bool = True
    confidence: str = "balanced"  # confident, humble, balanced
    traits: list[str] = field(default_factory=lambda: ["helpful", "accurate"])

    def to_dict(self) -> dict:
        return {
            "tone": self.tone, "verbosity": self.verbosity, "style": self.style,
            "humor": self.humor, "empathy": self.empathy, "confidence": self.confidence,
            "traits": self.traits,
        }


@dataclass
class Capability:
    name: str
    enabled: bool = True
    max_complexity: str = "high"  # low, medium, high
    tools_allowed: list[str] = field(default_factory=list)  # empty = all
    tools_blocked: list[str] = field(default_factory=list)
    requires_approval: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "enabled": self.enabled,
            "max_complexity": self.max_complexity,
            "tools_allowed": self.tools_allowed, "tools_blocked": self.tools_blocked,
            "requires_approval": self.requires_approval,
        }


@dataclass
class AgentProfile:
    id: str
    name: str
    description: str = ""
    system_prompt_override: str = ""
    personality: Personality = field(default_factory=Personality)
    capabilities: list[Capability] = field(default_factory=list)
    model_override: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "system_prompt_override": self.system_prompt_override,
            "personality": self.personality.to_dict(),
            "capabilities": [c.to_dict() for c in self.capabilities],
            "model_override": self.model_override,
            "max_tokens": self.max_tokens, "temperature": self.temperature,
            "tags": self.tags, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentProfile:
        personality = Personality(**data.get("personality", {}))
        capabilities = [Capability(**c) for c in data.get("capabilities", [])]
        return cls(
            id=data["id"], name=data["name"], description=data.get("description", ""),
            system_prompt_override=data.get("system_prompt_override", ""),
            personality=personality, capabilities=capabilities,
            model_override=data.get("model_override", ""),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def generate_system_prompt(self, base_prompt: str) -> str:
        """Generate a system prompt based on profile settings."""
        if self.system_prompt_override:
            return self.system_prompt_override

        parts = [base_prompt]
        p = self.personality

        style_directives = []
        if p.tone == "casual":
            style_directives.append("Use a casual, conversational tone.")
        elif p.tone == "formal":
            style_directives.append("Use formal language and proper grammar.")
        elif p.tone == "technical":
            style_directives.append("Use precise technical language.")

        if p.verbosity == "concise":
            style_directives.append("Keep responses short and to the point.")
        elif p.verbosity == "verbose":
            style_directives.append("Provide detailed, thorough explanations.")

        if p.style == "Socratic":
            style_directives.append("Ask guiding questions to help the user discover answers.")
        elif p.style == "collaborative":
            style_directives.append("Work with the user as a partner, suggesting options.")
        elif p.style == "instructional":
            style_directives.append("Teach and explain step by step.")

        if p.humor:
            style_directives.append("Use appropriate humor when it helps.")
        if p.empathy:
            style_directives.append("Show understanding and empathy for the user's situation.")

        if style_directives:
            parts.append("\n## Communication Style\n" + "\n".join(style_directives))

        if self.capabilities:
            cap_names = [c.name for c in self.capabilities if c.enabled]
            if cap_names:
                parts.append(f"\n## Specializations\n{', '.join(cap_names)}")

        return "\n".join(parts)


class ProfileManager:
    """Manages agent profiles and personas."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/profiles")
        self.profiles: dict[str, AgentProfile] = {}
        self._active_profile: Optional[str] = None
        self._load()
        if not self.profiles:
            self._create_defaults()

    def _create_defaults(self) -> None:
        self.profiles["default"] = AgentProfile(
            id="default", name="Xeno Default",
            description="Default professional agent profile",
            personality=Personality(
                tone="professional", verbosity="concise", style="direct",
                traits=["helpful", "accurate", "efficient"],
            ),
        )
        self.profiles["researcher"] = AgentProfile(
            id="researcher", name="Research Specialist",
            description="Thorough research and analysis profile",
            personality=Personality(
                tone="technical", verbosity="verbose", style="instructional",
                traits=["thorough", "analytical", "methodical"],
            ),
            capabilities=[
                Capability(name="research", max_complexity="high"),
                Capability(name="analysis", max_complexity="high"),
            ],
        )
        self.profiles["coder"] = AgentProfile(
            id="coder", name="Code Specialist",
            description="Code generation and debugging profile",
            personality=Personality(
                tone="technical", verbosity="moderate", style="direct",
                traits=["precise", "systematic", "clean-code"],
            ),
            capabilities=[
                Capability(name="coding", max_complexity="high"),
                Capability(name="debugging", max_complexity="high"),
            ],
        )
        self._save()

    def get_profile(self, profile_id: str) -> Optional[AgentProfile]:
        return self.profiles.get(profile_id)

    def create_profile(
        self, name: str, description: str = "",
        personality: Optional[Personality] = None,
        **kwargs,
    ) -> AgentProfile:
        import uuid
        profile = AgentProfile(
            id=f"prof_{uuid.uuid4().hex[:8]}",
            name=name, description=description,
            personality=personality or Personality(),
            **kwargs,
        )
        self.profiles[profile.id] = profile
        self._save()
        return profile

    def update_profile(self, profile_id: str, **kwargs) -> Optional[AgentProfile]:
        profile = self.profiles.get(profile_id)
        if not profile:
            return None
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        self._save()
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        if profile_id in self.profiles and profile_id != "default":
            del self.profiles[profile_id]
            if self._active_profile == profile_id:
                self._active_profile = "default"
            self._save()
            return True
        return False

    def set_active(self, profile_id: str) -> bool:
        if profile_id in self.profiles:
            self._active_profile = profile_id
            return True
        return False

    def get_active(self) -> AgentProfile:
        if self._active_profile:
            return self.profiles.get(self._active_profile, self.profiles["default"])
        return self.profiles.get("default", AgentProfile(id="default", name="Default"))

    def list_profiles(self) -> list[AgentProfile]:
        return list(self.profiles.values())

    def check_tool_allowed(self, profile: AgentProfile, tool_name: str) -> bool:
        for cap in profile.capabilities:
            if not cap.enabled:
                continue
            if cap.tools_blocked and tool_name in cap.tools_blocked:
                return False
            if cap.tools_allowed and tool_name not in cap.tools_allowed:
                continue
        return True

    def summary(self) -> str:
        return f"Profiles: {len(self.profiles)} total, active: {self._active_profile or 'default'}"

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "profiles.json").write_text(
            json.dumps({pid: p.to_dict() for pid, p in self.profiles.items()}, indent=2)
        )
        (self.data_dir / "active.txt").write_text(self._active_profile or "default")

    def _load(self) -> None:
        path = self.data_dir / "profiles.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.profiles = {k: AgentProfile.from_dict(v) for k, v in data.items()}
            except Exception:
                self.profiles = {}
        active_path = self.data_dir / "active.txt"
        if active_path.exists():
            self._active_profile = active_path.read_text().strip()
