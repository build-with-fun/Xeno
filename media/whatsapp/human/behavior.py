"""Human-like delays and typing/reading simulation.

Fixes the original code's issues:
- `simulate_typing` clicked the input box but never typed anything (dead code)
- `human_delay` used an overcomplicated loop that summed to ~delay anyway
- Reply delays were uniform random(0.5, 1.0)s — too fast for WhatsApp
- No per-word typing-speed model
"""
from __future__ import annotations

import random
import time
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class HumanBehavior:
    """Realistic human-behavior simulation."""

    def __init__(self) -> None:
        self.delay_min = settings.reply_delay_min
        self.delay_max = settings.reply_delay_max
        self.wpm_min = settings.typing_speed_wpm_min
        self.wpm_max = settings.typing_speed_wpm_max
        self.cpm_min = settings.reading_speed_cpm_min
        self.cpm_max = settings.reading_speed_cpm_max

    def simulate_reading(self, messages: list) -> None:
        """Pause as if reading the incoming messages.

        Models reading speed (chars per minute) with jitter, capped to a
        sensible max so very long messages don't block forever.
        """
        total_chars = sum(
            len(pm.get("content", "") if isinstance(pm, dict) else getattr(pm, "content", ""))
            for pm in messages
        )
        if total_chars == 0:
            time.sleep(random.uniform(0.3, 0.8))
            return
        cpm = random.uniform(self.cpm_min, self.cpm_max)
        delay = (total_chars / cpm) * 60.0
        # Jitter ±15%, clamp to [0.5, 8.0]
        delay *= random.uniform(0.85, 1.15)
        delay = max(0.5, min(8.0, delay))
        time.sleep(delay)

    def simulate_typing_delay(self, reply_text: str) -> float:
        """Compute how long to 'type' the reply before sending.

        Returns the duration in seconds (caller is responsible for actually
        triggering WhatsApp's typing indicator, e.g. by pressing keys).
        """
        word_count = max(1, len(reply_text.split()))
        wpm = random.uniform(self.wpm_min, self.wpm_max)
        duration = (word_count / wpm) * 60.0
        # Jitter ±10%, cap at 12s (WhatsApp hides the indicator after ~10s)
        duration *= random.uniform(0.9, 1.1)
        return min(12.0, duration)

    def reply_delay(self) -> float:
        """Pre-reply delay (between reading and starting to type)."""
        return random.uniform(self.delay_min, self.delay_max)

    def jittered_sleep(self, base: float, jitter_pct: float = 0.15) -> None:
        """Sleep for `base` seconds ± jitter_pct."""
        delay = base * random.uniform(1 - jitter_pct, 1 + jitter_pct)
        time.sleep(max(0.0, delay))

    def scan_interval(self) -> float:
        """Randomized interval between sidebar scans."""
        return random.uniform(settings.scan_interval_min, settings.scan_interval_max)

    def post_send_pause(self) -> None:
        """Brief pause after sending a message before closing the chat."""
        self.jittered_sleep(0.5, 0.3)

    def pre_open_pause(self) -> None:
        """Brief pause before opening a chat (avoids robotic rapid clicking)."""
        self.jittered_sleep(0.3, 0.5)


# Singleton
human = HumanBehavior()
