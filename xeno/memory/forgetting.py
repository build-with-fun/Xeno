"""FadeMem forgetting curves."""
from __future__ import annotations
import math, time
from dataclasses import dataclass, field
from enum import Enum

class MemoryDurability(str, Enum):
    VOLATILE="volatile"; SHORT_TERM="short_term"; LONG_TERM="long_term"
    PERMANENT="permanent"; IMMORTAL="immortal"

DECAY_PARAMS = {
    MemoryDurability.VOLATILE: {"beta":1.5,"lambda":0.10},
    MemoryDurability.SHORT_TERM: {"beta":1.2,"lambda":0.05},
    MemoryDurability.LONG_TERM: {"beta":0.8,"lambda":0.01},
    MemoryDurability.PERMANENT: {"beta":0.5,"lambda":0.001},
    MemoryDurability.IMMORTAL: {"beta":0.0,"lambda":0.0},
}

@dataclass
class ForgettingState:
    importance: float; durability: MemoryDurability
    created_at: float; last_accessed: float
    access_count: int = 0; last_review_at: float = 0
    review_stage: int = 0; boosted: float = 0.0

class ForgettingEngine:
    @staticmethod
    def strength(state, now=None):
        if state.durability == MemoryDurability.IMMORTAL:
            return min(1.0, state.importance + state.boosted)
        now = now or time.time()
        p = DECAY_PARAMS[state.durability]
        hours = max(0.0, (now - state.last_accessed) / 3600.0)
        decay = math.exp(-p["lambda"] * (hours ** p["beta"]))
        sr = min(0.3, state.review_stage * 0.05)
        freq = min(0.2, math.log10(state.access_count + 1) * 0.1)
        return max(0.0, min(1.0, state.importance * decay + sr + freq + state.boosted))
    @staticmethod
    def recommend_durability(importance, memory_type=""):
        if memory_type in ("user_identity","user_preferences","core_skill"):
            return MemoryDurability.IMMORTAL
        if importance >= 0.9: return MemoryDurability.PERMANENT
        if importance >= 0.6: return MemoryDurability.LONG_TERM
        if importance >= 0.3: return MemoryDurability.SHORT_TERM
        return MemoryDurability.VOLATILE
