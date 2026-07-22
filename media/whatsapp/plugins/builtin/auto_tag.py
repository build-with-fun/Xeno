"""Auto-tag plugin.

Automatically tags contacts based on message content. Tags can be used
for filtering, analytics, and targeted broadcasts.

Example rules:
  - Message contains "meeting" → tag "work"
  - Message contains "family" → tag "personal"
  - Message contains "invoice" → tag "business"
  - Sentiment is angry → tag "needs-attention"
"""
from __future__ import annotations

import re
from typing import Optional

from media.whatsapp.plugins.base import Plugin, PluginContext, PluginResult, HookPoint
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

_DEFAULT_RULES = [
    # Business / work
    {"pattern": r"\b(meeting|deadline|project|report|invoice|contract|proposal)\b",
     "tag": "work", "flags": re.IGNORECASE},
    # Personal / family
    {"pattern": r"\b(family|mom|dad|wife|husband|kids|birthday|anniversary)\b",
     "tag": "personal", "flags": re.IGNORECASE},
    # Finance
    {"pattern": r"\b(payment|money|transfer|bank|account|loan|salary|bill)\b",
     "tag": "finance", "flags": re.IGNORECASE},
    # Urgent
    {"pattern": r"\b(urgent|emergency|asap|immediately|right now|critical)\b",
     "tag": "urgent", "flags": re.IGNORECASE},
    # Health
    {"pattern": r"\b(doctor|hospital|sick|medicine|appointment|health)\b",
     "tag": "health", "flags": re.IGNORECASE},
    # Travel
    {"pattern": r"\b(flight|airport|hotel|booking|trip|travel|vacation)\b",
     "tag": "travel", "flags": re.IGNORECASE},
    # Tech
    {"pattern": r"\b(code|bug|server|deploy|api|database|programming)\b",
     "tag": "tech", "flags": re.IGNORECASE},
]


class AutoTagPlugin(Plugin):
    """Automatically tags contacts based on message content."""

    name = "auto_tag"
    version = "1.0.0"
    description = "Auto-tags contacts based on message keywords"
    hooks = {HookPoint.AFTER_DECISION}
    default_config = {
        "rules": _DEFAULT_RULES,
        "max_tags_per_contact": 20,
    }

    def after_decision(self, ctx: PluginContext) -> PluginResult:
        """Tag the contact based on message content."""
        full_text = " ".join(m.get("content", "") for m in ctx.messages)
        if not full_text:
            return PluginResult()

        tags_to_add = set()
        for rule in self.config["rules"]:
            pattern = rule["pattern"]
            flags = rule.get("flags", 0)
            tag = rule["tag"]
            if re.search(pattern, full_text, flags):
                tags_to_add.add(tag)

        # Also tag based on sentiment
        sentiment = ctx.metadata.get("sentiment")
        if sentiment == "angry":
            tags_to_add.add("needs-attention")
        elif sentiment == "positive":
            tags_to_add.add("happy")

        if not tags_to_add:
            return PluginResult()

        # Apply tags
        try:
            from media.whatsapp.db.repo import ContactRepo
            for tag in tags_to_add:
                ContactRepo.add_tag(ctx.contact_name, tag)
            logger.info(
                f"[AutoTag] Tagged {ctx.contact_name}: {', '.join(tags_to_add)}"
            )
        except Exception as e:
            logger.warning(f"[AutoTag] Failed to tag: {e}")

        return PluginResult(metadata={"tags_added": list(tags_to_add)})
