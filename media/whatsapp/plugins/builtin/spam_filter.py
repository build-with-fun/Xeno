"""Bayesian spam detection plugin.

Uses a simple Naive Bayes classifier to detect spam messages. Spam is
either auto-rejected (skip_reply) or escalated for human review.

Trains on-the-fly: when a message is manually rejected via the admin
API, it's added to the spam corpus. Approved messages train as ham.
"""
from __future__ import annotations

import math
import re
import threading
from collections import defaultdict
from typing import Optional

from media.whatsapp.plugins.base import Plugin, PluginContext, PluginResult, HookPoint
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class SpamFilterPlugin(Plugin):
    """Bayesian spam filter with on-the-fly training."""

    name = "spam_filter"
    version = "1.0.0"
    description = "Bayesian spam detection — auto-rejects or escalates spam"
    hooks = {HookPoint.BEFORE_DECISION}
    default_config = {
        "spam_threshold": 0.85,        # Score above this = spam
        "review_threshold": 0.6,       # Score above this = review
        "auto_skip_spam": True,        # Skip reply entirely for high-score spam
        "min_training_samples": 10,    # Need this many samples before filtering
    }

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._lock = threading.RLock()
        # word -> {"spam": count, "ham": count}
        self._word_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"spam": 0, "ham": 0})
        self._spam_count = 0
        self._ham_count = 0
        self._load_training_data()

    def _load_training_data(self) -> None:
        """Load training data from DB."""
        try:
            from media.whatsapp.db.repo import PluginStateRepo
            state = PluginStateRepo.get(self.name)
            if state and state.state:
                data = state.state
                self._word_counts = defaultdict(
                    lambda: {"spam": 0, "ham": 0},
                    data.get("word_counts", {}),
                )
                self._spam_count = data.get("spam_count", 0)
                self._ham_count = data.get("ham_count", 0)
                logger.info(
                    f"[SpamFilter] Loaded training data: "
                    f"{self._spam_count} spam, {self._ham_count} ham"
                )
        except Exception as e:
            logger.warning(f"[SpamFilter] Could not load training data: {e}")

    def _save_training_data(self) -> None:
        """Persist training data to DB."""
        try:
            from media.whatsapp.db.repo import PluginStateRepo
            PluginStateRepo.update_state(self.name, {
                "word_counts": dict(self._word_counts),
                "spam_count": self._spam_count,
                "ham_count": self._ham_count,
            })
        except Exception as e:
            logger.warning(f"[SpamFilter] Could not save training data: {e}")

    def before_decision(self, ctx: PluginContext) -> PluginResult:
        """Score messages for spam probability."""
        if self._spam_count + self._ham_count < self.config["min_training_samples"]:
            return PluginResult()  # Not enough training data

        full_text = " ".join(m.get("content", "") for m in ctx.messages)
        if not full_text:
            return PluginResult()

        score = self._classify(full_text)
        ctx.metadata["spam_score"] = score

        if score >= self.config["spam_threshold"]:
            logger.warning(
                f"[SpamFilter] Spam detected from {ctx.contact_name} "
                f"(score={score:.2f}): {full_text[:60]}"
            )
            if self.config["auto_skip_spam"]:
                return PluginResult(skip_reply=True, metadata={"spam_detected": True})
            # Otherwise force approval
            if ctx.decision:
                modified = dict(ctx.decision)
                modified["needs_approval"] = True
                modified["reason"] = f"Spam detected (score={score:.2f})"
                return PluginResult(modified_decision=modified)

        elif score >= self.config["review_threshold"]:
            logger.info(
                f"[SpamFilter] Possible spam from {ctx.contact_name} "
                f"(score={score:.2f})"
            )
            if ctx.decision:
                modified = dict(ctx.decision)
                modified["needs_approval"] = True
                modified["reason"] = f"Possible spam (score={score:.2f})"
                return PluginResult(modified_decision=modified)

        return PluginResult()

    def _classify(self, text: str) -> float:
        """Naive Bayes classification. Returns P(spam | text) in [0, 1]."""
        words = self._tokenize(text)
        if not words:
            return 0.0

        # Log probabilities to avoid underflow
        log_spam = math.log(max(self._spam_count, 1) / max(self._spam_count + self._ham_count, 2))
        log_ham = math.log(max(self._ham_count, 1) / max(self._spam_count + self._ham_count, 2))

        for word in words:
            counts = self._word_counts.get(word, {"spam": 0, "ham": 0})
            # Laplace smoothing
            p_word_given_spam = (counts["spam"] + 1) / (self._spam_count + 2)
            p_word_given_ham = (counts["ham"] + 1) / (self._ham_count + 2)
            log_spam += math.log(p_word_given_spam)
            log_ham += math.log(p_word_given_ham)

        # Convert log-odds to probability
        if log_spam > log_ham:
            return 1.0 / (1.0 + math.exp(log_ham - log_spam))
        else:
            return math.exp(log_spam - log_ham) / (1.0 + math.exp(log_spam - log_ham))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into lowercase tokens."""
        return re.findall(r"[a-z]+", text.lower())

    def train_spam(self, text: str) -> None:
        """Train a message as spam."""
        with self._lock:
            for word in self._tokenize(text):
                self._word_counts[word]["spam"] += 1
            self._spam_count += 1
            self._save_training_data()

    def train_ham(self, text: str) -> None:
        """Train a message as ham (not spam)."""
        with self._lock:
            for word in self._tokenize(text):
                self._word_counts[word]["ham"] += 1
            self._ham_count += 1
            self._save_training_data()
