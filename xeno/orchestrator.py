"""24/7 Orchestrator — ties together AlwaysOn agents, Scheduler, and the main agent.

This is the brain behind autonomous operation:
- Manages all 24/7 agents (WhatsApp auto-replier, social media, business)
- Self-schedules health checks
- Handles "full business mode" — extracts data, manages social media, WhatsApp
- Any agent can start/stop other agents via the orchestrator
- Supports flexible scheduling for all agent types
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class BusinessProfile:
    """What the user's business needs handled autonomously."""
    name: str = ""
    social_media: list[str] = field(default_factory=list)  # twitter, instagram, linkedin, etc.
    whatsapp_enabled: bool = False
    email_enabled: bool = False
    website_enabled: bool = False
    check_interval_minutes: int = 30
    auto_reply: bool = True
    content_schedule: dict[str, Any] = field(default_factory=dict)
    health_check_interval_minutes: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """The orchestrator manages all 24/7 agents and scheduling.

    Features:
    - Start/stop WhatsApp auto-replier
    - Start/stop social media manager
    - Full business mode (autonomous operation for days/weeks)
    - Self-scheduling health checks
    - Any agent can control other agents
    - Flexible scheduling: after_delay, interval, daily, weekly, yearly, cron
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = data_dir / "business_profiles.json"
        self._profiles: dict[str, BusinessProfile] = {}
        self._agent_executor: Callable | None = None
        self._always_on = None
        self._scheduler = None
        self._dynamic_system = None
        self._loaded = False

    def set_dependencies(self, always_on, scheduler, agent_executor: Callable | None = None, dynamic_system=None) -> None:
        """Wire up the always-on manager, scheduler, agent executor, and dynamic system."""
        self._always_on = always_on
        self._scheduler = scheduler
        self._agent_executor = agent_executor
        self._dynamic_system = dynamic_system

    async def initialize(self) -> None:
        """Load profiles and start autonomous operations."""
        if self._loaded:
            return
        self._load_profiles()
        self._loaded = True

    def _load_profiles(self) -> None:
        if not self.profiles_file.exists():
            return
        try:
            data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
            for name, pdata in data.items():
                self._profiles[name] = BusinessProfile(**pdata)
        except Exception as e:
            logger.error(f"Failed to load business profiles: {e}")

    def _save_profiles(self) -> None:
        data = {name: {
            "name": p.name,
            "social_media": p.social_media,
            "whatsapp_enabled": p.whatsapp_enabled,
            "email_enabled": p.email_enabled,
            "website_enabled": p.website_enabled,
            "check_interval_minutes": p.check_interval_minutes,
            "auto_reply": p.auto_reply,
            "content_schedule": p.content_schedule,
            "health_check_interval_minutes": p.health_check_interval_minutes,
            "metadata": p.metadata,
        } for name, p in self._profiles.items()}
        self.profiles_file.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    # =========================================================================
    # BUSINESS MODE — Full autonomous operation
    # =========================================================================

    async def start_business_mode(
        self,
        profile_name: str = "default",
        social_media: list[str] | None = None,
        whatsapp: bool = True,
        health_check_minutes: int = 60,
        check_all_minutes: int = 30,
    ) -> str:
        """Start full autonomous business mode.

        This will:
        1. Start all discovered agents with always_on: true
        2. Schedule daily/weekly check-ins
        3. Schedule health checks
        """
        results = []

        profile = BusinessProfile(
            name=profile_name,
            social_media=social_media or [],
            whatsapp_enabled=whatsapp,
            check_interval_minutes=check_all_minutes,
            health_check_interval_minutes=health_check_minutes,
            auto_reply=True,
        )
        self._profiles[profile_name] = profile
        self._save_profiles()

        # Start all discovered always-on agents
        if self._always_on and self._dynamic_system:
            descriptors = self._dynamic_system.registry.list_agents(enabled_only=True)
            for desc in descriptors:
                if getattr(desc, "always_on", False):
                    result = self._always_on.create_agent_from_descriptor(desc, auto_start=True)
                    results.append(result)

        # Schedule daily check-ins
        if self._scheduler:
            self._scheduler.create(
                name=f"daily_check_{profile_name}",
                prompt=f"Run daily business check for profile '{profile_name}': "
                       f"verify all 24/7 agents are healthy, review today's activity, "
                       f"check for any issues that need attention.",
                schedule_type="daily",
                schedule_config={"hour": 9, "minute": 0},
            )
            results.append("Scheduled daily check-in at 9:00 AM")

            self._scheduler.create(
                name=f"weekly_summary_{profile_name}",
                prompt=f"Generate weekly business summary for '{profile_name}': "
                       f"compile all activity from the past week, identify patterns, "
                       f"suggest improvements, report any recurring issues.",
                schedule_type="weekly",
                schedule_config={"weekday": 0, "hour": 10, "minute": 0},
            )
            results.append("Scheduled weekly summary on Monday at 10:00 AM")

        return f"Business mode started for '{profile_name}':\n" + "\n".join(results)

    async def stop_business_mode(self, profile_name: str = "default") -> str:
        """Stop all autonomous business operations."""
        results = []

        profile = self._profiles.get(profile_name)
        if not profile:
            return f"No business profile found: '{profile_name}'"

        # Stop all 24/7 agents
        if self._always_on:
            agents = self._always_on.list_agents()
            for agent_info in agents:
                if agent_info["state"] == "running":
                    result = await self._always_on.stop_agent(agent_info["id"])
                    results.append(result)

        # Remove scheduled tasks for this profile
        if self._scheduler:
            for tid, task in list(self._scheduler.tasks.items()):
                if profile_name in task.name:
                    self._scheduler.delete(tid)
                    results.append(f"Removed schedule: {task.name}")

        del self._profiles[profile_name]
        self._save_profiles()

        return f"Stopped business mode for '{profile_name}':\n" + "\n".join(results)

    # =========================================================================
    # DYNAMIC AGENT MANAGEMENT — Create/start/stop any discovered agent
    # =========================================================================

    async def start_discovered_agent(self, agent_id: str) -> str:
        """Start a discovered agent as a 24/7 agent."""
        if not self._always_on or not self._dynamic_system:
            return "Always-on manager or dynamic system not available"

        descriptor = self._dynamic_system.registry.get_agent(agent_id)
        if not descriptor:
            return f"Agent '{agent_id}' not found in dynamic registry"

        return self._always_on.create_agent_from_descriptor(descriptor, auto_start=True)

    async def start_all_always_on_agents(self) -> str:
        """Start all discovered agents with always_on: true."""
        if not self._always_on or not self._dynamic_system:
            return "Always-on manager or dynamic system not available"

        results = []
        descriptors = self._dynamic_system.registry.list_agents(enabled_only=True)
        for desc in descriptors:
            if getattr(desc, "always_on", False):
                result = self._always_on.create_agent_from_descriptor(desc, auto_start=True)
                results.append(result)

        return "\n".join(results) if results else "No always-on agents found"

    # =========================================================================
    # AGENT CONTROL — Any agent can control other agents
    # =========================================================================

    async def start_agent(self, agent_name_or_id: str) -> str:
        """Start a 24/7 agent by name or ID."""
        if not self._always_on:
            return "Always-on manager not available"

        # Try by ID first
        if agent_name_or_id in self._always_on._agents:
            return await self._always_on.start_agent(agent_name_or_id)

        # Try by name
        for aid, agent in self._always_on._agents.items():
            if agent.config.name.lower() == agent_name_or_id.lower():
                return await self._always_on.start_agent(aid)

        return f"Agent '{agent_name_or_id}' not found"

    async def stop_agent(self, agent_name_or_id: str) -> str:
        """Stop a 24/7 agent by name or ID."""
        if not self._always_on:
            return "Always-on manager not available"

        if agent_name_or_id in self._always_on._agents:
            return await self._always_on.stop_agent(agent_name_or_id)

        for aid, agent in self._always_on._agents.items():
            if agent.config.name.lower() == agent_name_or_id.lower():
                return await self._always_on.stop_agent(aid)

        return f"Agent '{agent_name_or_id}' not found"

    # =========================================================================
    # FLEXIBLE SCHEDULING — Create any schedule type
    # =========================================================================

    def schedule_after(
        self,
        name: str,
        prompt: str,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        seconds: int = 0,
    ) -> str:
        """Schedule a task to run after a delay."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="after_delay",
            schedule_config={"minutes": minutes, "hours": hours, "days": days, "seconds": seconds},
        )

    def schedule_every(
        self,
        name: str,
        prompt: str,
        minutes: int = 0,
        hours: int = 0,
        seconds: int = 0,
    ) -> str:
        """Schedule a recurring task at a fixed interval."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="interval",
            schedule_config={"minutes": minutes, "hours": hours, "seconds": seconds},
        )

    def schedule_daily(self, name: str, prompt: str, hour: int = 9, minute: int = 0) -> str:
        """Schedule a daily task at a specific time."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="daily",
            schedule_config={"hour": hour, "minute": minute},
        )

    def schedule_weekly(
        self, name: str, prompt: str, weekday: int = 0, hour: int = 9, minute: int = 0,
    ) -> str:
        """Schedule a weekly task. weekday: 0=Monday, 6=Sunday."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="weekly",
            schedule_config={"weekday": weekday, "hour": hour, "minute": minute},
        )

    def schedule_monthly(
        self, name: str, prompt: str, day: int = 1, hour: int = 9, minute: int = 0,
    ) -> str:
        """Schedule a monthly task."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="monthly",
            schedule_config={"day": day, "hour": hour, "minute": minute},
        )

    def schedule_yearly(
        self, name: str, prompt: str, month: int = 1, day: int = 1, hour: int = 9, minute: int = 0,
    ) -> str:
        """Schedule a yearly task."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="yearly",
            schedule_config={"month": month, "day": day, "hour": hour, "minute": minute},
        )

    def schedule_cron(
        self,
        name: str,
        prompt: str,
        minute: str = "*",
        hour: str = "*",
        day_of_month: str = "*",
        month: str = "*",
        day_of_week: str = "*",
    ) -> str:
        """Schedule with a cron-like expression. Use '*' for 'every'."""
        if not self._scheduler:
            return "Scheduler not available"
        return self._scheduler.create(
            name=name,
            prompt=prompt,
            schedule_type="cron",
            schedule_config={
                "minute": minute,
                "hour": hour,
                "day_of_month": day_of_month,
                "month": month,
                "day_of_week": day_of_week,
            },
        )

    # =========================================================================
    # STATUS & HEALTH
    # =========================================================================

    async def get_full_status(self) -> dict[str, Any]:
        """Get comprehensive status of all 24/7 operations."""
        agents = self._always_on.list_agents() if self._always_on else []
        schedules = self._scheduler.list_all() if self._scheduler else "No scheduler"
        health = await self._always_on.health_check_all() if self._always_on else {}

        return {
            "agents": agents,
            "schedules": schedules,
            "health": health,
            "profiles": list(self._profiles.keys()),
            "summary": self._always_on.get_summary() if self._always_on else "No 24/7 manager",
        }

    def get_status_string(self) -> str:
        """Get a human-readable status string."""
        lines = []
        if self._always_on:
            lines.append(self._always_on.get_summary())
            agents = self._always_on.list_agents()
            for a in agents:
                lines.append(
                    f"  [{a['state'].upper()}] {a['name']} ({a['type']}) "
                    f"- tasks: {a['tasks_completed']}, errors: {a['errors']}"
                )
        if self._scheduler:
            lines.append(f"\nSchedules: {self._scheduler.list_all()}")
        if self._profiles:
            lines.append(f"\nBusiness profiles: {', '.join(self._profiles.keys())}")
        return "\n".join(lines) if lines else "No 24/7 operations active"
