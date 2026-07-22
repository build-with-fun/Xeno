"""Brain — LLM-driven intent analyzer. NO REGEX. NO KEYWORDS.

The LLM is the brain. Every user message goes through analyze() which returns
a structured Intent describing what the user wants + what to remember + what to schedule.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    QUICK_REPLY = "quick_reply"
    MEMORY_STORE = "memory_store"
    MEMORY_QUERY = "memory_query"
    AUTO_SCHEDULE = "auto_schedule"
    SCHEDULING = "scheduling"
    QUICK_RESEARCH = "quick_research"
    TASK = "task"
    COMMAND = "command"
    SELF_MODIFY = "self_modify"
    EMOTIONAL = "emotional"


@dataclass
class ExtractedFact:
    subject: str
    predicate: str
    object: str
    category: str
    confidence: float = 0.8
    raw: str = ""


@dataclass
class ScheduleSuggestion:
    name: str
    prompt: str
    schedule_type: str  # once|daily|weekly|monthly|yearly|after_delay
    config: dict
    reason: str = ""
    auto_create: bool = True


@dataclass
class Intent:
    intent_type: IntentType
    confidence: float
    reasoning: str = ""
    draft_response: str = ""
    facts: list[ExtractedFact] = field(default_factory=list)
    schedule_suggestions: list[ScheduleSuggestion] = field(default_factory=list)
    estimated_seconds: int = 0
    task_approach: str = ""
    self_mod_target: str = ""
    self_mod_description: str = ""
    emotion: str = "neutral"
    needs_full_agent: bool = False
    spawn_background_task: bool = False
    timestamp: float = field(default_factory=time.time)
    sub_intents: list["Intent"] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["intent_type"] = self.intent_type.value
        if self.sub_intents:
            d["sub_intents"] = [si.to_dict() for si in self.sub_intents]
        return d


SYSTEM_PROMPT = """You are the BRAIN of Xeno, a general-purpose AI assistant.

Your job: analyze the user's message and output ONLY valid JSON.

=== INTENT TYPES ===
quick_reply     — casual chat, greetings, opinions, simple facts known to you
memory_store    — user shares personal info (name, birthday, preferences, etc.)
memory_query    — user asks what you remember about them
auto_schedule   — birthday/anniversary/date mentioned → create yearly schedule
scheduling      — "remind me to X" → create schedule entry
quick_research  — factual questions ("who is X", "what is Y", "weather in Z")
task            — real actions (open, close, create, build, send, install, run)
self_modify     — user wants to change YOUR code/tools/behavior
emotional       — user expresses feelings

=== EXAMPLES ===

"hi" → quick_reply
{"intent_type":"quick_reply","confidence":0.95,"reasoning":"greeting","draft_response":"Hey! How can I help?"}

"my name is John" → memory_store
{"intent_type":"memory_store","confidence":0.95,"reasoning":"user shared name","draft_response":"Nice to meet you, John!","facts":[{"subject":"user","predicate":"name","object":"John","category":"identity","confidence":0.99,"raw":"my name is John"}]}

"my birthday is April 21" → auto_schedule
{"intent_type":"auto_schedule","confidence":0.95,"reasoning":"birthday → yearly wish","draft_response":"Got it! I'll wish you happy birthday every year.","facts":[{"subject":"user","predicate":"birthday","object":"April 21","category":"schedule","confidence":0.99,"raw":"my birthday is April 21"}],"schedule_suggestions":[{"name":"Birthday wish","prompt":"Wish user happy birthday","schedule_type":"yearly","config":{"month":4,"day":21,"hour":9,"minute":0},"reason":"user birthday","auto_create":true}]}

"what's my name?" → memory_query
{"intent_type":"memory_query","confidence":0.9,"reasoning":"user asking what I remember","draft_response":"","estimated_seconds":0}

"what is the weather in London" → quick_research
{"intent_type":"quick_research","confidence":0.9,"reasoning":"factual weather lookup","draft_response":"","estimated_seconds":15,"needs_full_agent":true}

"open youtube" → task
{"intent_type":"task","confidence":0.95,"reasoning":"user wants browser action","task_approach":"Open YouTube in browser","estimated_seconds":15,"needs_full_agent":true,"spawn_background_task":true}

"close chrome" → task
{"intent_type":"task","confidence":0.95,"reasoning":"user wants to close browser","task_approach":"Close Chrome browser","estimated_seconds":10,"needs_full_agent":true,"spawn_background_task":true}

"remind me to drink water every hour" → scheduling
{"intent_type":"scheduling","confidence":0.95,"reasoning":"recurring reminder","draft_response":"I'll remind you to drink water every hour!","schedule_suggestions":[{"name":"Drink water","prompt":"Time to drink water! Stay hydrated.","schedule_type":"interval","config":{"interval_seconds":3600},"reason":"user requested hourly reminder","auto_create":true}],"estimated_seconds":0}

"add a tool that generates QR codes" → self_modify
{"intent_type":"self_modify","confidence":0.9,"reasoning":"user wants new capability","self_mod_target":"xeno/tools/qr_code.py","self_mod_description":"Create a QR code generator tool","needs_full_agent":true}

"i'm feeling sad today" → emotional
{"intent_type":"emotional","confidence":0.8,"reasoning":"user expressing sadness","draft_response":"I'm sorry you're feeling down. Want to talk about it?","emotion":"sad"}

=== COMPOUND QUERIES ===
When the user asks MULTIPLE things in one message, output a PRIMARY intent + sub_intents array.

"what is the weather in england and tell me who is ayanokoji kiyotaka and close chrome"
{"intent_type":"quick_research","confidence":0.95,"reasoning":"compound query with research and task","draft_response":"","sub_intents":[{"intent_type":"quick_research","confidence":0.95,"reasoning":"weather forecast","draft_response":"","estimated_seconds":15,"task_approach":"Check weather in England","needs_full_agent":true,"spawn_background_task":false},{"intent_type":"quick_research","confidence":0.9,"reasoning":"character lookup","draft_response":"","estimated_seconds":15,"task_approach":"Look up Ayanokoji Kiyotaka","needs_full_agent":true,"spawn_background_task":false},{"intent_type":"task","confidence":0.95,"reasoning":"browser action","task_approach":"Close Chrome browser","estimated_seconds":10,"needs_full_agent":true,"spawn_background_task":true}]}

"open youtube and search for cats" → compound
{"intent_type":"task","confidence":0.9,"reasoning":"compound: open + search","sub_intents":[{"intent_type":"task","confidence":0.95,"reasoning":"open youtube","task_approach":"Open YouTube","estimated_seconds":10,"needs_full_agent":true,"spawn_background_task":true},{"intent_type":"quick_research","confidence":0.9,"reasoning":"search for cat videos","estimated_seconds":15,"needs_full_agent":true,"spawn_background_task":false}]}

=== CRITICAL RULES ===
- For RESEARCH questions (weather, who is X, what is Y) → quick_research.
- For ACTIONS (open, close, create, send) → task.
- For COMPOUND queries with research + actions → use sub_intents array.
- Research sub_intents: needs_full_agent=true, spawn_background_task=false (answered while user waits).
- Task sub_intents: needs_full_agent=true, spawn_background_task=true (background execution).
- Always set estimated_seconds: 10-30 for quick tasks, 60+ for complex ones.
- Output ONLY valid JSON. No other text before or after.
- NEVER use markdown code fences."""


class Brain:
    """The LLM-driven intent analyzer."""

    def __init__(
        self,
        llm: Callable[[str, str], Awaitable[str]],
        max_retries: int = 2,
        timeout_seconds: int = 15,
    ):
        self.llm = llm
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    async def analyze(
        self,
        user_input: str,
        conversation_context: str = "",
        user_profile_summary: str = "",
    ) -> Intent:
        """Analyze a user message and return an Intent."""
        user_msg = f"User message: {user_input}"
        if user_profile_summary and "(nothing known yet" not in user_profile_summary:
            user_msg += f"\n\nWhat I already know about the user:\n{user_profile_summary}"

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                import asyncio
                response = await asyncio.wait_for(
                    self.llm(SYSTEM_PROMPT, user_msg),
                    timeout=self.timeout_seconds,
                )
                intent = self._parse_response(response, user_input)
                if intent is not None:
                    return intent
                logger.warning(f"Brain: parse failed (attempt {attempt+1}, response: {response[:200]})")
            except asyncio.TimeoutError:
                last_error = "LLM timed out"
                logger.warning(f"Brain LLM timed out (attempt {attempt + 1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Brain LLM failed (attempt {attempt + 1}): {e}")

        logger.warning(f"Brain fallback. Last error: {last_error}")
        return self._fallback_intent(user_input)

    def _make_fallback(self, text: str, reason: str) -> Intent:
        return Intent(
            intent_type=IntentType.QUICK_REPLY,
            confidence=0.5,
            reasoning=reason,
            draft_response=text[:500],
            facts=[],
            schedule_suggestions=[],
            estimated_seconds=0,
            task_approach="",
            self_mod_target="",
            self_mod_description="",
            emotion="neutral",
            needs_full_agent=False,
            spawn_background_task=False,
        )

    def _parse_response(self, response: str, original_input: str) -> Optional[Intent]:
        if not response:
            logger.debug("Brain: empty response")
            return None
        text = response.strip()
        # Handle ```json fences and plain ``` fences
        if text.startswith("```"):
            lines = text.split("\n")
            first = lines[0].strip().lower() if lines else ""
            if first in ("```", "```json", "```json\n"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])
            except (json.JSONDecodeError, Exception):
                pass
        if data is None:
            # If response is conversational (no JSON at all), treat as valid quick_reply
            logger.debug("Brain: conversational response, treating as quick_reply")
            return Intent(
                intent_type=IntentType.QUICK_REPLY,
                confidence=0.7,
                reasoning="LLM gave conversational response, treated as quick reply",
                draft_response=text[:500],
                facts=[],
                schedule_suggestions=[],
                estimated_seconds=0,
                task_approach="",
                self_mod_target="",
                self_mod_description="",
                emotion="neutral",
                needs_full_agent=False,
                spawn_background_task=False,
            )
        try:
            intent_type_str = data.get("intent_type", "quick_reply")
            try:
                intent_type = IntentType(intent_type_str)
            except ValueError:
                intent_type = IntentType.QUICK_REPLY

            def parse_single(d: dict) -> Intent:
                it_str = d.get("intent_type", "quick_reply")
                try:
                    it = IntentType(it_str)
                except ValueError:
                    it = IntentType.QUICK_REPLY
                facts = [
                    ExtractedFact(
                        subject=f.get("subject", "user"),
                        predicate=f.get("predicate", "is"),
                        object=f.get("object", ""),
                        category=f.get("category", "fact"),
                        confidence=f.get("confidence", 0.8),
                        raw=f.get("raw", ""),
                    )
                    for f in d.get("facts", [])
                ]
                schedules = [
                    ScheduleSuggestion(
                        name=s.get("name", "unnamed"),
                        prompt=s.get("prompt", ""),
                        schedule_type=s.get("schedule_type", "once"),
                        config=s.get("config", {}),
                        reason=s.get("reason", ""),
                        auto_create=s.get("auto_create", False),
                    )
                    for s in d.get("schedule_suggestions", [])
                ]
                sub_raw = d.get("sub_intents", [])
                sub_intents = [parse_single(si) for si in sub_raw] if isinstance(sub_raw, list) else []
                return Intent(
                    intent_type=it,
                    confidence=float(d.get("confidence", 0.5)),
                    reasoning=d.get("reasoning", ""),
                    draft_response=d.get("draft_response", ""),
                    facts=facts,
                    schedule_suggestions=schedules,
                    estimated_seconds=int(d.get("estimated_seconds", 0)),
                    task_approach=d.get("task_approach", ""),
                    self_mod_target=d.get("self_mod_target", ""),
                    self_mod_description=d.get("self_mod_description", ""),
                    emotion=d.get("emotion", "neutral"),
                    needs_full_agent=bool(d.get("needs_full_agent", False)),
                    spawn_background_task=bool(d.get("spawn_background_task", False)),
                    sub_intents=sub_intents,
                )

            return parse_single(data)
        except Exception as e:
            logger.error(f"Failed to parse intent: {e}")
            return None

    def _fallback_intent(self, user_input: str) -> Intent:
        text = user_input.strip()
        if text.startswith("/"):
            return Intent(
                intent_type=IntentType.COMMAND,
                confidence=1.0,
                reasoning="starts with /",
            )
        return Intent(
            intent_type=IntentType.QUICK_REPLY,
            confidence=0.3,
            reasoning="LLM unavailable, defaulting to quick reply",
            draft_response=f"I heard you say: {user_input}. (LLM is currently unavailable)",
            emotion="neutral",
        )
