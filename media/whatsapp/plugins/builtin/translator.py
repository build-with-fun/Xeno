"""Auto-translation plugin.

Detects the language of incoming messages and translates them to English
for the AI to process. Translates the reply back to the contact's language.

Uses the AI router for translation (free with most providers).
"""
from __future__ import annotations

from typing import Optional

from media.whatsapp.plugins.base import Plugin, PluginContext, PluginResult, HookPoint
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

_LANG_DETECT_PROMPT = """Detect the language of this text. Reply with ONLY the ISO 639-1 code (e.g., "en", "ur", "es", "ar"). If unclear, reply "en".

Text: {text}"""

_TRANSLATE_PROMPT = """Translate this text to {target_lang}. Preserve meaning, tone, and any names/numbers. Reply with ONLY the translation, no explanation.

Text: {text}"""


class TranslatorPlugin(Plugin):
    """Auto-translates messages to/from the contact's language."""

    name = "translator"
    version = "1.0.0"
    description = "Auto-translates messages to/from the contact's language"
    hooks = {HookPoint.BEFORE_DECISION, HookPoint.BEFORE_REPLY}
    default_config = {
        "target_language": "en",  # Translate incoming to this for AI
        "enabled_for": [],  # Empty = all contacts
        "disabled_for": [],  # Contacts to skip
    }

    def before_decision(self, ctx: PluginContext) -> PluginResult:
        """Translate incoming messages to English for the AI."""
        if ctx.contact_name in self.config.get("disabled_for", []):
            return PluginResult()

        # Get contact's language from DB
        contact_lang = self._get_contact_language(ctx.contact_name)
        if contact_lang is None or contact_lang == self.config["target_language"]:
            return PluginResult()

        # Translate each message
        from media.whatsapp.ai.router import router
        modified = []
        for msg in ctx.messages:
            content = msg.get("content", "")
            if not content:
                modified.append(msg)
                continue
            prompt = _TRANSLATE_PROMPT.format(
                target_lang=self.config["target_language"], text=content[:2000],
            )
            translated = router.simple_text(prompt, max_chars=5000)
            if translated:
                msg = dict(msg)
                msg["original_content"] = content
                msg["original_language"] = contact_lang
                msg["content"] = translated
            modified.append(msg)

        return PluginResult(modified_messages=modified, metadata={
            "translated_from": contact_lang,
            "translated_to": self.config["target_language"],
        })

    def before_reply(self, ctx: PluginContext) -> PluginResult:
        """Translate the reply back to the contact's language."""
        if not ctx.reply or ctx.contact_name in self.config.get("disabled_for", []):
            return PluginResult()

        contact_lang = self._get_contact_language(ctx.contact_name)
        if contact_lang is None or contact_lang == self.config["target_language"]:
            return PluginResult()

        from media.whatsapp.ai.router import router
        prompt = _TRANSLATE_PROMPT.format(
            target_lang=contact_lang, text=ctx.reply[:2000],
        )
        translated = router.simple_text(prompt, max_chars=5000)
        if translated:
            return PluginResult(modified_reply=translated)
        return PluginResult()

    def _get_contact_language(self, contact_name: str) -> Optional[str]:
        """Get or detect the contact's language."""
        try:
            from media.whatsapp.db.repo import ContactRepo
            contact = ContactRepo.get_by_name(contact_name)
            if contact and contact.language:
                return contact.language
        except Exception:
            pass
        return None
