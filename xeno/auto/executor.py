"""Auto-executor — stores facts + creates schedules automatically."""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Optional

from xeno.brain.intent import Intent
from xeno.profile.manager import UserProfile

logger = logging.getLogger(__name__)


class AutoExecutor:
    """Executes the brain's decisions automatically.

    For every user message, the brain returns an Intent. This class:
    1. Stores all extracted facts in the user profile + unified memory
    2. Creates all auto_create=true schedules
    3. Returns a summary of what was stored/created
    """

    def __init__(
        self,
        profile: UserProfile,
        memory_store_fn: Optional[Callable[[str, dict], Awaitable[bool]]] = None,
        schedule_create_fn: Optional[Callable[[str, str, str, str], Awaitable[str]]] = None,
    ):
        self.profile = profile
        self.memory_store_fn = memory_store_fn
        self.schedule_create_fn = schedule_create_fn

    async def execute(self, intent: Intent) -> dict:
        """Execute the intent's side effects (memory + schedules)."""
        result = {
            "facts_stored": [],
            "schedules_created": [],
            "errors": [],
        }

        # 1. Store all facts in profile + memory
        # Deduplicate facts: if same subject+predicate appears multiple times, keep only last
        seen_keys = set()
        deduped = []
        for fact in reversed(intent.facts):
            key = (fact.subject, fact.predicate)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(fact)
        deduped.reverse()
        for fact in deduped:
            try:
                # Store in structured profile
                self.profile.update_from_fact(
                    subject=fact.subject,
                    predicate=fact.predicate,
                    obj=fact.object,
                    category=fact.category,
                )
                # Also store in unified memory (for vector search later)
                if self.memory_store_fn is not None:
                    try:
                        await self.memory_store_fn(
                            f"{fact.subject} {fact.predicate} {fact.object}",
                            {
                                "kind": "user_fact",
                                "subject": fact.subject,
                                "predicate": fact.predicate,
                                "object": fact.object,
                                "category": fact.category,
                                "raw": fact.raw,
                            },
                        )
                    except Exception as e:
                        result["errors"].append(f"memory store: {e}")
                result["facts_stored"].append({
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "object": fact.object,
                    "category": fact.category,
                })
            except Exception as e:
                logger.error(f"Failed to store fact {fact}: {e}")
                result["errors"].append(f"fact store: {e}")

        # 2. Create auto schedules
        for sched in intent.schedule_suggestions:
            if not sched.auto_create:
                continue
            if self.schedule_create_fn is None:
                result["errors"].append("scheduler not available")
                continue
            try:
                config_json = json.dumps(sched.config)
                msg = await self.schedule_create_fn(
                    sched.name, sched.prompt, sched.schedule_type, config_json
                )
                # Also record in profile
                self.profile.add_schedule_event(
                    sched.name, json.dumps(sched.config), sched.schedule_type
                )
                self.profile.add_history(f"Auto-scheduled: {sched.name}", category="schedule")
                result["schedules_created"].append({
                    "name": sched.name,
                    "schedule_type": sched.schedule_type,
                    "config": sched.config,
                    "result": msg,
                })
            except Exception as e:
                logger.error(f"Failed to create schedule {sched.name}: {e}")
                result["errors"].append(f"schedule create: {e}")

        return result
