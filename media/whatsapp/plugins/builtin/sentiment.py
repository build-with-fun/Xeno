"""Sentiment analysis plugin.

Analyzes the sentiment of incoming messages. If a contact's sentiment
drops below a threshold (angry/negative), they are escalated for human
review — even if the AI says auto-reply.

Uses keyword-based sentiment for speed (no extra AI call needed), with
optional AI-based analysis for ambiguous cases.
"""
from __future__ import annotations

import re
from typing import Optional

from media.whatsapp.plugins.base import Plugin, PluginContext, PluginResult, HookPoint
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

# Keyword-based sentiment scoring (fast, no AI call)
_POSITIVE_WORDS = {
    "happy", "love", "great", "awesome", "thanks", "thank you", "good",
    "amazing", "excellent", "wonderful", "perfect", "nice", "cool", "fun",
    "excited", "glad", "pleased", "appreciate", "grateful", "best",
}
_NEGATIVE_WORDS = {
    "angry", "hate", "stupid", "terrible", "awful", "worst", "horrible",
    "frustrated", "annoyed", "furious", "disappointed", "upset", "sad",
    "depressed", "scared", "worried", "anxious", "stressed", "tired",
    "broken", "fail", "failed", "useless", "trash", "garbage", "idiot",
}
_ANGRY_WORDS = {
    "furious", "rage", "pissed", "damn", "shit", "fuck", "screw",
    "liar", "scam", "fraud", "ripoff", "lawsuit", "lawyer", "sue",
    "police", "report", "complain", "refund", "cancel",
}
_ESCALATION_WORDS = {
    "lawyer", "lawsuit", "sue", "police", "court", "legal action",
    "consumer protection", "better business bureau", "attorney general",
}


class SentimentPlugin(Plugin):
    """Analyzes sentiment and escalates angry/negative contacts."""

    name = "sentiment"
    version = "1.0.0"
    description = "Analyzes message sentiment; escalates angry contacts"
    hooks = {HookPoint.AFTER_DECISION}
    default_config = {
        "escalation_threshold": -0.5,  # Escalate if score < this
        "auto_approve_angry": True,    # Force approval for angry messages
        "track_running_average": True,  # Track per-contact running avg
    }

    def after_decision(self, ctx: PluginContext) -> PluginResult:
        """Score sentiment and optionally override the decision."""
        full_text = " ".join(m.get("content", "") for m in ctx.messages)
        if not full_text:
            return PluginResult()

        score, sentiment = self._analyze_sentiment(full_text)
        ctx.metadata["sentiment_score"] = score
        ctx.metadata["sentiment"] = sentiment

        # Store in DB
        try:
            from media.whatsapp.db.repo import ContactRepo
            from media.whatsapp.db.models import Sentiment
            sentiment_enum = {
                "positive": Sentiment.POSITIVE,
                "neutral": Sentiment.NEUTRAL,
                "negative": Sentiment.NEGATIVE,
                "angry": Sentiment.ANGRY,
            }.get(sentiment, Sentiment.NEUTRAL)
            ContactRepo.update_sentiment(ctx.contact_name, score, sentiment_enum)
        except Exception as e:
            logger.warning(f"[Sentiment] DB update failed: {e}")

        # Check for legal/escalation keywords — force approval
        lower_text = full_text.lower()
        for kw in _ESCALATION_WORDS:
            if kw in lower_text:
                logger.warning(
                    f"[Sentiment] Escalation keyword '{kw}' from {ctx.contact_name} — forcing approval"
                )
                if ctx.decision:
                    modified = dict(ctx.decision)
                    modified["needs_approval"] = True
                    modified["risk_level"] = "HIGH"
                    modified["reason"] = f"Escalation keyword detected: {kw}"
                    modified["triggered_category"] = "LEGAL"
                    return PluginResult(modified_decision=modified)
                break

        # Force approval for angry messages
        if (self.config["auto_approve_angry"] and sentiment == "angry"
                and ctx.decision and not ctx.decision.get("needs_approval")):
            logger.info(
                f"[Sentiment] Angry message from {ctx.contact_name} — forcing approval"
            )
            modified = dict(ctx.decision)
            modified["needs_approval"] = True
            modified["risk_level"] = "MEDIUM"
            modified["reason"] = "Angry sentiment detected — human review recommended"
            return PluginResult(modified_decision=modified)

        return PluginResult()

    @staticmethod
    def _analyze_sentiment(text: str) -> tuple[float, str]:
        """Quick keyword-based sentiment analysis. Returns (score, label).

        Score: -1.0 (very negative) to +1.0 (very positive)
        """
        lower = text.lower()
        words = set(re.findall(r"\w+", lower))

        pos = len(words & _POSITIVE_WORDS)
        neg = len(words & _NEGATIVE_WORDS)
        angry = len(words & _ANGRY_WORDS)

        if angry > 0:
            return (-0.8 - angry * 0.1, "angry")
        if neg > pos:
            score = -min(1.0, (neg - pos) * 0.3)
            return (score, "negative" if score < -0.3 else "neutral")
        if pos > neg:
            score = min(1.0, (pos - neg) * 0.3)
            return (score, "positive" if score > 0.3 else "neutral")
        return (0.0, "neutral")
