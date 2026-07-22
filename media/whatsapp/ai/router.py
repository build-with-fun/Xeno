"""AI router: provider selection, fallback, and dual-provider consensus.

Fixes the original code's issues:
- Single direction fallback (Gemini -> Groq) with no consensus check
- If Gemini flagged a message, Groq was only asked as "second opinion"
  AFTER the first flag — meaning if Gemini was down and Groq ran first,
  no second opinion was sought.
- No priority ordering, no per-capability routing (vision vs text)
"""
from __future__ import annotations

import itertools
import threading
import time
from typing import Optional

from media.whatsapp.ai.base import AIProvider, ProviderCapability, registry
from media.whatsapp.ai.gemini import GeminiProvider
from media.whatsapp.ai.groq import GroqProvider
from media.whatsapp.ai.openai_compat import OpenAICompatProvider
from media.whatsapp.ai.prompts import DECISION_SYSTEM_PROMPT, build_reply_system_prompt, build_summary_prompt
from media.whatsapp.config import settings
from media.whatsapp.core.types import Decision, Persona, ProcessedMessage, RiskLevel, DecisionCategory
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)

# Safe fallback when ALL providers fail
SAFE_FALLBACK = Decision(
    needs_approval=False,
    risk_level=RiskLevel.LOW,
    is_retraction=False,
    reason="AI unavailable — safe auto-reply fallback.",
    retraction_reply="",
    confidence=0.5,
    triggered_category=DecisionCategory.CASUAL,
    provider="fallback",
)


class AIRouter:
    """Routes AI calls across multiple providers with round-robin and fallback."""

    def __init__(self) -> None:
        self._providers: list[AIProvider] = []
        self._rr_counter = itertools.count()
        self._lock = threading.Lock()
        self._init_providers()

    def _init_providers(self) -> None:
        """Instantiate one provider instance per API key."""
        for key in settings.gemini_api_keys:
            try:
                self._providers.append(GeminiProvider(key))
            except Exception as e:
                logger.warning(f"[Router] Skipping Gemini key: {e}")
        for key in settings.groq_api_keys:
            try:
                self._providers.append(GroqProvider(key))
            except Exception as e:
                logger.warning(f"[Router] Skipping Groq key: {e}")
        for key in settings.openai_api_keys:
            try:
                self._providers.append(OpenAICompatProvider(key))
            except Exception as e:
                logger.warning(f"[Router] Skipping OpenAI key: {e}")
        logger.info(
            f"[Router] Initialized {len(self._providers)} provider instances "
            f"(Gemini={len(settings.gemini_api_keys)}, "
            f"Groq={len(settings.groq_api_keys)}, "
            f"OpenAI={len(settings.openai_api_keys)})"
        )

    @property
    def providers(self) -> list[AIProvider]:
        return list(self._providers)

    def _available(self, capability: Optional[ProviderCapability] = None) -> list[AIProvider]:
        """Return providers not on cooldown, optionally filtered by capability."""
        out = []
        for p in self._providers:
            if p.is_on_cooldown() or not p.is_available():
                continue
            if capability and capability not in p.capabilities:
                continue
            out.append(p)
        return out

    def _next_provider(self, capability: Optional[ProviderCapability] = None) -> Optional[AIProvider]:
        """Round-robin pick of the next available provider."""
        avail = self._available(capability)
        if not avail:
            return None
        with self._lock:
            idx = next(self._rr_counter) % len(avail)
        return avail[idx]

    # ── Simple text (used for summarization) ─────────────────────────────────
    def simple_text(self, prompt: str, max_chars: int) -> str:
        """Try providers in round-robin until one succeeds."""
        tried: set[int] = set()
        for _ in range(len(self._providers)):
            p = self._next_provider()
            if p is None or id(p) in tried:
                break
            tried.add(id(p))
            result = p.simple_text(prompt, max_chars)
            if result:
                metrics.inc("ai_simple_success", provider=p.name)
                return result
        logger.warning("[Router] simple_text: all providers exhausted")
        return ""

    # ── Summarization helper ─────────────────────────────────────────────────
    def summarize(self, old_summary: str, new_messages: str) -> str:
        """Generate a conversation summary."""
        prompt = build_summary_prompt(old_summary, new_messages)
        # Try every available provider (text capability) until one succeeds
        for p in self._available(None):
            result = p.simple_text(prompt, settings.gemini_max_chars)
            if result:
                metrics.inc("ai_summary_success", provider=p.name)
                return result
        logger.warning("[Router] summarize: all providers exhausted")
        return ""

    # ── Decision (with dual-provider consensus) ──────────────────────────────
    def decide(
        self, messages_text: str, history_str: str,
    ) -> Decision:
        """Run the decision engine with dual-provider consensus.

        Strategy:
        1. Pick a primary provider (round-robin), ask for a decision.
        2. If primary says "needs_approval", ask a DIFFERENT provider for
           a second opinion. Only escalate to approval if BOTH agree.
        3. If primary says "auto-reply", trust it (false positives are
           recoverable; false negatives on the safety side are not — but
           we can't ask for second opinion on every message without
           doubling API costs).
        4. If all providers fail, return SAFE_FALLBACK (auto-reply).
        """
        user_content = f"RECENT HISTORY:\n{history_str}\n\nCURRENT MESSAGES:\n{messages_text}"

        primary = self._next_provider(ProviderCapability.JSON)
        if primary is None:
            primary = self._next_provider()
        if primary is None:
            logger.warning("[Router] decide: no providers available")
            return SAFE_FALLBACK

        primary_decision = primary.structured_decision(
            DECISION_SYSTEM_PROMPT, user_content, settings.gemini_max_chars,
        )
        if primary_decision is None:
            # Primary failed entirely — try one fallback
            secondary = self._next_provider(ProviderCapability.JSON)
            if secondary and secondary is not primary:
                secondary_decision = secondary.structured_decision(
                    DECISION_SYSTEM_PROMPT, user_content, settings.gemini_max_chars,
                )
                if secondary_decision:
                    metrics.inc("decision_success", provider=secondary.name, role="fallback")
                    return Decision.from_dict(secondary_decision, provider=secondary.name)
            logger.warning("[Router] decide: all providers failed -> SAFE_FALLBACK")
            return SAFE_FALLBACK

        metrics.inc("decision_success", provider=primary.name, role="primary")

        # Retractions: trust the primary, no second opinion needed
        if primary_decision.get("is_retraction"):
            return Decision.from_dict(primary_decision, provider=primary.name)

        # Auto-reply: trust the primary
        if not primary_decision.get("needs_approval"):
            return Decision.from_dict(primary_decision, provider=primary.name)

        # Approval flagged: get second opinion from a DIFFERENT provider
        secondary = self._next_provider(ProviderCapability.JSON)
        if secondary and secondary is not primary:
            secondary_decision = secondary.structured_decision(
                DECISION_SYSTEM_PROMPT, user_content, settings.gemini_max_chars,
            )
            if secondary_decision and not secondary_decision.get("needs_approval"):
                logger.info(
                    "[Router] Secondary disagrees with primary -> auto-reply"
                    f" (primary={primary.name}, secondary={secondary.name})"
                )
                metrics.inc("decision_consensus_disagreement", primary=primary.name, secondary=secondary.name)
                return Decision.from_dict(secondary_decision, provider=secondary.name)

        return Decision.from_dict(primary_decision, provider=primary.name)

    # ── Reply generation ─────────────────────────────────────────────────────
    def reply(
        self, persona: Persona, history_str: str,
        messages: list[ProcessedMessage], custom_ctx: str = "",
    ) -> str:
        """Generate a reply using available providers."""
        system_prompt = build_reply_system_prompt(persona, history_str, custom_ctx)
        # Convert ProcessedMessage to dict for the provider
        msg_dicts = []
        has_image = False
        for pm in messages:
            msg_dicts.append({
                "label": pm.label,
                "content": pm.content,
                "image_bytes": pm.image_bytes,
                "mimetype": getattr(pm, 'mimetype', None) or "image/jpeg",
            })
            if pm.image_bytes:
                has_image = True

        # Try vision-capable providers first if we have an image
        capability = ProviderCapability.VISION if has_image else None
        tried_instances: set[int] = set()
        for _ in range(len(self._providers)):
            p = self._next_provider(capability)
            if p is None or id(p) in tried_instances:
                # Fall back to any provider
                p = self._next_provider()
                if p is None or id(p) in tried_instances:
                    break
            tried_instances.add(id(p))
            reply = p.reply(system_prompt, msg_dicts, None, settings.gemini_max_chars)
            if reply:
                metrics.inc("reply_success", provider=p.name)
                return reply

        # All providers failed — return persona's fallback
        logger.error(
            f"[Router] reply: all providers failed, using persona fallback: "
            f"{persona.fallback_reply!r}"
        )
        return persona.fallback_reply


# Singleton
router = AIRouter()
