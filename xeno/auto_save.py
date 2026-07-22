"""Auto-save system — automatically detects and persists everything.

No user action needed. On every interaction, this system:
  - Extracts user preferences ("I prefer X", "I like Y", "Don't do Z")
  - Detects and stores facts the user mentions
  - Summarizes conversations and stores in episodic memory
  - Detects task patterns ("the user often asks about X")
  - Tracks the user's working style and habits
  - Maintains a user profile that improves over time

All data is stored persistently and used to personalize future interactions.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class UserPreference:
    key: str
    value: str
    confidence: float = 0.5
    source: str = "auto_detected"
    first_seen: float = field(default_factory=time.time)
    last_confirmed: float = field(default_factory=time.time)
    times_confirmed: int = 1

    def to_dict(self) -> dict:
        return {
            "key": self.key, "value": self.value,
            "confidence": self.confidence, "source": self.source,
            "first_seen": self.first_seen, "last_confirmed": self.last_confirmed,
            "times_confirmed": self.times_confirmed,
        }


@dataclass
class UserFact:
    id: str
    content: str
    category: str = "general"
    confidence: float = 0.5
    source: str = "conversation"
    timestamp: float = field(default_factory=time.time)
    times_reinforced: int = 1

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content,
            "category": self.category, "confidence": self.confidence,
            "source": self.source, "ts": self.timestamp,
            "reinforced": self.times_reinforced,
        }


@dataclass
class ConversationSummary:
    id: str
    summary: str
    topics: list[str] = field(default_factory=list)
    user_sentiment: str = "neutral"
    key_decisions: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "summary": self.summary,
            "topics": self.topics, "sentiment": self.user_sentiment,
            "decisions": self.key_decisions, "ts": self.timestamp,
            "msgs": self.message_count,
        }


@dataclass
class TaskPattern:
    pattern: str
    count: int = 1
    last_seen: float = field(default_factory=time.time)
    avg_success: float = 1.0
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern, "count": self.count,
            "last_seen": self.last_seen, "avg_success": self.avg_success,
            "tools": self.tools_used,
        }


# --- Preference detection patterns ---
PREF_PATTERNS = [
    (r"(?:i prefer|i like|i want|make it|use|i want you to|always) (.+)", "preference"),
    (r"(?:don'?t|never|stop|avoid|no more) (.+)", "negative_preference"),
    (r"(?:my name is|i'?m called|i am) (\w+)", "user_name"),
    (r"(?:i work as|i'?m a|my job is|i do) (.+)", "user_role"),
    (r"(?:i use|i work with|my stack is|technologies?:?) (.+)", "tech_stack"),
]

FACT_PATTERNS = [
    (r"(?:the fact is|fun fact|did you know|important:) (.+)", "fact"),
    (r"(?:remember that|note:|keep in mind) (.+)", "note"),
    (r"(?:the answer is|result is|output is|value is) (.+)", "result"),
]


class AutoSave:
    """Automatically detects and saves user data from conversations.

    Runs on every interaction with zero user intervention.
    Extracts preferences, facts, summaries, and patterns.
    Maintains a persistent user profile.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/auto_save")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.preferences: list[UserPreference] = []
        self.facts: list[UserFact] = []
        self.summaries: list[ConversationSummary] = []
        self.task_patterns: list[TaskPattern] = []
        self.user_profile: dict[str, Any] = {
            "name": "",
            "role": "",
            "tech_stack": [],
            "communication_style": "unknown",
            "total_interactions": 0,
            "first_seen": time.time(),
            "last_seen": time.time(),
        }

        self._conversation_buffer: list[dict[str, str]] = []
        self._load()

    # --- Main entry point (called on every interaction) ---

    def process_interaction(self, user_input: str, response: str) -> dict[str, Any]:
        """Analyze a user interaction and auto-save anything valuable.

        Returns a dict of what was detected and saved.
        """
        detections: dict[str, Any] = {
            "preferences": [],
            "facts": [],
            "profile_updates": [],
        }

        # 1. Detect preferences
        prefs = self._extract_preferences(user_input)
        for key, value, pref_type in prefs:
            if pref_type == "negative_preference":
                key = f"avoid_{key}"
            saved = self._save_preference(key, value)
            if saved:
                detections["preferences"].append({"key": key, "value": value})

        # 2. Detect facts
        facts = self._extract_facts(user_input)
        for fact_content, category in facts:
            saved = self._save_fact(fact_content, category)
            if saved:
                detections["facts"].append(fact_content[:80])

        # 3. Update conversation buffer
        self._conversation_buffer.append({"role": "user", "content": user_input})
        self._conversation_buffer.append({"role": "assistant", "content": response})

        # 4. Update user profile
        profile_updates = self._update_profile(user_input)
        detections["profile_updates"] = profile_updates

        # 5. Update interaction count
        self.user_profile["total_interactions"] += 1
        self.user_profile["last_seen"] = time.time()

        # 6. Auto-summarize every 10 messages
        if len(self._conversation_buffer) >= 20:
            self._auto_summarize()

        self._save()
        return detections

    # --- Preference extraction (delegated to agent's LLM brain) ---

    def _extract_preferences(self, text: str) -> list[tuple[str, str, str]]:
        """Extract preferences using pattern matching as fast fallback.
        The agent's _smart_memorize() handles the primary LLM-based extraction."""
        return []  # LLM handles this in agent._smart_memorize()

    def _derive_preference_key(self, value: str) -> str:
        """Derive a short preference key from the value."""
        words = value.split()[:5]
        return "_".join(words)

    def _save_preference(self, key: str, value: str) -> bool:
        """Save or reinforce a preference. Returns True if new/updated."""
        for pref in self.preferences:
            if pref.key == key:
                pref.times_confirmed += 1
                pref.confidence = min(1.0, pref.confidence + 0.1)
                pref.last_confirmed = time.time()
                return False

        self.preferences.append(UserPreference(
            key=key, value=value, confidence=0.6,
            source="auto_detected",
        ))
        return True

    # --- Fact extraction (delegated to agent's LLM brain) ---

    def _extract_facts(self, text: str) -> list[tuple[str, str]]:
        """Extract facts using pattern matching as fast fallback.
        The agent's _smart_memorize() handles the primary LLM-based extraction."""
        return []  # LLM handles this in agent._smart_memorize()

    def _save_fact(self, content: str, category: str = "general") -> bool:
        """Save a fact, reinforcing if already known."""
        content_lower = content.lower()
        for fact in self.facts:
            if content_lower in fact.content.lower() or fact.content.lower() in content_lower:
                fact.times_reinforced += 1
                fact.confidence = min(1.0, fact.confidence + 0.1)
                return False

        self.facts.append(UserFact(
            id=f"fact_{uuid.uuid4().hex[:8]}",
            content=content, category=category, confidence=0.6,
        ))
        return True

    # --- Profile updates ---

    def _update_profile(self, text: str) -> list[str]:
        updates = []
        text_lower = text.lower()

        # Name detection
        name_match = re.search(r"(?:my name is|i'?m called|i am) (\w+)", text_lower)
        if name_match:
            name = name_match.group(1).strip().title()
            if name and self.user_profile["name"] != name:
                self.user_profile["name"] = name
                updates.append(f"name={name}")

        # Role detection
        role_match = re.search(r"(?:i work as|i'?m a|my job is|i do) (.+?)(?:\.|!|$|,)", text_lower)
        if role_match:
            role = role_match.group(1).strip()
            if role and self.user_profile["role"] != role:
                self.user_profile["role"] = role
                updates.append(f"role={role}")

        # Tech stack detection
        tech_match = re.search(r"(?:i use|i work with|my stack is|technologies?:?) (.+?)(?:\.|!|$)", text_lower)
        if tech_match:
            techs = [t.strip() for t in re.split(r',|\band\b', tech_match.group(1)) if t.strip()]
            for tech in techs:
                if tech not in self.user_profile["tech_stack"]:
                    self.user_profile["tech_stack"].append(tech)
                    updates.append(f"tech+={tech}")

        return updates

    # --- Auto-summarization ---

    def _auto_summarize(self) -> None:
        """Summarize the conversation buffer and clear it."""
        if not self._conversation_buffer:
            return

        messages = self._conversation_buffer[:]
        self._conversation_buffer = []

        # Extract topics from user messages
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        all_text = " ".join(user_msgs)

        # Simple topic extraction (most common meaningful words)
        words = re.findall(r'\b[a-z]{4,}\b', all_text.lower())
        word_freq: dict[str, int] = {}
        for w in words:
            if w not in ("this", "that", "with", "from", "have", "been", "were", "what", "when", "where", "which", "about", "would", "could", "should", "there", "their", "than", "then", "them", "they", "your", "just"):
                word_freq[w] = word_freq.get(w, 0) + 1
        topics = sorted(word_freq, key=word_freq.get, reverse=True)[:5]

        # Simple sentiment detection
        positive_words = {"good", "great", "thanks", "perfect", "excellent", "nice", "love", "like", "yes", "awesome"}
        negative_words = {"bad", "wrong", "error", "fail", "broken", "hate", "no", "terrible", "awful", "bug"}
        pos = sum(1 for w in words if w in positive_words)
        neg = sum(1 for w in words if w in negative_words)
        if pos > neg:
            sentiment = "positive"
        elif neg > pos:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        summary_text = f"Conversation about {', '.join(topics[:3])} ({len(messages)} messages)"

        summary = ConversationSummary(
            id=f"summ_{uuid.uuid4().hex[:8]}",
            summary=summary_text,
            topics=topics,
            user_sentiment=sentiment,
            message_count=len(messages),
        )
        self.summaries.append(summary)

    # --- Task pattern detection ---

    def detect_task_pattern(self, task_description: str) -> Optional[TaskPattern]:
        """Check if this task matches a known pattern."""
        task_words = " ".join(task_description.lower().split()[:6])
        for pattern in self.task_patterns:
            if self._pattern_overlap(task_words, pattern.pattern) > 0.6:
                pattern.count += 1
                pattern.last_seen = time.time()
                self._save()
                return pattern
        return None

    def record_task_pattern(self, description: str, tools: list[str] = None, success: bool = True) -> TaskPattern:
        pattern_words = " ".join(description.lower().split()[:6])
        existing = self.detect_task_pattern(description)
        if existing:
            existing.count += 1
            existing.last_seen = time.time()
            if tools:
                for t in tools:
                    if t not in existing.tools_used:
                        existing.tools_used.append(t)
            self._save()
            return existing

        tp = TaskPattern(
            pattern=pattern_words,
            tools_used=tools or [],
        )
        self.task_patterns.append(tp)
        self._save()
        return tp

    def _pattern_overlap(self, a: str, b: str) -> float:
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / max(len(words_a | words_b), 1)

    # --- Getters for the agent to use ---

    def get_user_context(self) -> str:
        """Get a string to inject into the agent's context about the user."""
        parts = []
        if self.user_profile["name"]:
            parts.append(f"User name: {self.user_profile['name']}")
        if self.user_profile["role"]:
            parts.append(f"User role: {self.user_profile['role']}")
        if self.user_profile["tech_stack"]:
            parts.append(f"Tech stack: {', '.join(self.user_profile['tech_stack'])}")
        if self.preferences:
            top_prefs = sorted(self.preferences, key=lambda p: p.confidence, reverse=True)[:5]
            prefs_str = "; ".join(f"{p.key}={p.value}" for p in top_prefs)
            parts.append(f"Preferences: {prefs_str}")
        if self.facts:
            top_facts = sorted(self.facts, key=lambda f: f.confidence, reverse=True)[:5]
            facts_str = "; ".join(f.content[:60] for f in top_facts)
            parts.append(f"Known facts: {facts_str}")
        if self.summaries:
            last = self.summaries[-1]
            parts.append(f"Recent topics: {', '.join(last.topics[:3])}")
        parts.append(f"Interactions: {self.user_profile['total_interactions']}")
        return "\n".join(parts) if parts else "No user data yet."

    def get_preference(self, key: str) -> Optional[str]:
        for p in self.preferences:
            if p.key == key or key in p.key:
                return p.value
        return None

    def has_preference(self, key: str) -> bool:
        return self.get_preference(key) is not None

    def get_facts(self, category: str = "", limit: int = 20) -> list[UserFact]:
        if category:
            return [f for f in self.facts if f.category == category][:limit]
        return self.facts[:limit]

    def summary(self) -> str:
        return (
            f"AutoSave: {len(self.preferences)} prefs, {len(self.facts)} facts, "
            f"{len(self.summaries)} summaries, {len(self.task_patterns)} task patterns | "
            f"User: {self.user_profile.get('name', '?')} ({self.user_profile['total_interactions']} interactions)"
        )

    # --- Persistence ---

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "preferences.json").write_text(
            json.dumps([p.to_dict() for p in self.preferences], indent=2)
        )
        (self.data_dir / "facts.json").write_text(
            json.dumps([f.to_dict() for f in self.facts], indent=2)
        )
        (self.data_dir / "summaries.json").write_text(
            json.dumps([s.to_dict() for s in self.summaries[-100:]], indent=2)
        )
        (self.data_dir / "task_patterns.json").write_text(
            json.dumps([t.to_dict() for t in self.task_patterns], indent=2)
        )
        (self.data_dir / "profile.json").write_text(
            json.dumps(self.user_profile, indent=2)
        )

    def _load(self) -> None:
        for name, cls, target in [
            ("preferences.json", UserPreference, "preferences"),
            ("facts.json", UserFact, "facts"),
            ("summaries.json", ConversationSummary, "summaries"),
            ("task_patterns.json", TaskPattern, "task_patterns"),
        ]:
            path = self.data_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    setattr(self, target, [cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__}) for d in data])
                except Exception:
                    pass
        profile_path = self.data_dir / "profile.json"
        if profile_path.exists():
            try:
                loaded = json.loads(profile_path.read_text())
                self.user_profile.update(loaded)
            except Exception:
                pass
