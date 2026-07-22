"""LLM-driven Response Generator — REAL conversational responses, not templates.

BEFORE_WORK: The agent's ACTUAL answer about what it's going to do.
  "I'll open YouTube in your browser for you." (not "On it — I'll handle that now.")

AFTER_WORK: The ACTUAL result of what was done.
  "I've opened YouTube in your default browser. You should see it now." (not "Done! Here's what I did.")

The middle agent: lightweight LLM call for quick questions while a task runs.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from xeno.brain.intent import Intent, IntentType
from xeno.profile.manager import UserProfile

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates natural language responses using the LLM."""

    def __init__(
        self,
        llm: Callable[[str, str], Awaitable[str]],
        profile: UserProfile,
    ):
        self.llm = llm
        self.profile = profile

    def _is_json(self, text: str) -> bool:
        return bool(text) and text.strip().startswith("{")

    async def generate_quick_reply(self, user_input: str, intent: Intent, extra_context: str = "") -> str:
        """Generate a quick reply for chat, opinions, simple questions."""
        if intent.draft_response and len(intent.draft_response) > 10 and not self._is_json(intent.draft_response):
            return intent.draft_response
        profile_summary = self.profile.summary()
        if extra_context:
            profile_summary += f"\n\n{extra_context[:800]}"
        system = (
            "You are Xeno, a personal AI assistant.\n"
            "Reply briefly and naturally using the profile and context below.\n"
            "If the user asks about themselves (name, birthday, preferences), answer directly.\n"
            "If they ask about someone in the contact list, answer from that data.\n"
            "If they ask a general question or make small talk, answer naturally.\n"
            "1-3 sentences max. Output ONLY your reply."
        )
        user = f"Profile & contacts:\n{profile_summary}\n\nUser said: {user_input}\n\nYour reply:"
        try:
            return await self.llm(system, user)
        except Exception as e:
            return f"Hey — I hear you. ({e})"

    async def generate_emotional_reply(self, user_input: str, intent: Intent) -> str:
        if intent.draft_response and len(intent.draft_response) > 10 and not self._is_json(intent.draft_response):
            return intent.draft_response
        system = (
            "You are Xeno. The user is expressing an emotion. Reply with empathy in 1-2 sentences. "
            f"Detected emotion: {intent.emotion}. Output ONLY your reply."
        )
        user = f"User said: {user_input}\n\nYour reply:"
        try:
            return await self.llm(system, user)
        except Exception:
            return "I hear you. Want me to take over anything?"

    async def generate_memory_store_reply(self, user_input: str, intent: Intent, exec_result: dict) -> str:
        # Only use draft_response if facts were actually stored
        stored_count = len(exec_result.get("facts_stored", []))
        if stored_count > 0 and intent.draft_response and len(intent.draft_response) > 10 and not self._is_json(intent.draft_response):
            if exec_result.get("schedules_created") and "schedule" not in intent.draft_response.lower():
                sched_names = [s["name"] for s in exec_result["schedules_created"]]
                return intent.draft_response + f" (I've also set up: {', '.join(sched_names)})"
            return intent.draft_response
        facts_str = "; ".join(f"{f['subject']} {f['predicate']} {f['object']}" for f in exec_result.get("facts_stored", []))
        sched_str = "; ".join(f"{s['name']} ({s['schedule_type']})" for s in exec_result.get("schedules_created", []))
        system = (
            "You are Xeno. The user just told you something personal. "
            "You've stored it in memory. Reply warmly in 1-2 sentences confirming you'll remember. "
            "If a schedule was auto-created (like a birthday wish), mention it naturally. "
            "Output ONLY your reply."
        )
        user = (
            f"What I know about the user:\n{self.profile.summary()}\n\n"
            f"User said: {user_input}\n"
            f"What I stored: {facts_str}\n"
            f"What I scheduled: {sched_str or 'nothing'}\n\n"
            f"Your reply:"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                return reply
        except Exception:
            pass
        return "Got it — I'll remember that."

    async def generate_before_work(self, user_input: str, intent: Any = None, memory_context: str = "", extra_context: str = "") -> str:
        """REAL before-work answer — says what WILL be done, naturally.

        "I'll open YouTube for you." (future tense, not present)
        Includes profile name + memory context + extra context (contacts) for personalized responses.
        """
        profile_summary = self.profile.summary()
        name = ""
        if "Name:" in profile_summary:
            for line in profile_summary.split("\n"):
                if line.startswith("Name:"):
                    name = line.replace("Name:", "").strip()
                    break

        user_context = ""
        if name:
            user_context += f"User's name: {name}\n"
        if profile_summary and "(nothing known yet" not in profile_summary:
            user_context += f"About the user:\n{profile_summary[:300]}\n"
        if extra_context:
            user_context += f"Known contacts and context:\n{extra_context[:1200]}\n"
        if memory_context:
            user_context += f"Memory context:\n{memory_context[:500]}\n"

        intent_hint = ""
        if intent is not None:
            it = getattr(intent, 'intent_type', None)
            if it:
                intent_hint = f"Intent type: {it.value if hasattr(it, 'value') else it}\n"
            approach = getattr(intent, 'task_approach', '') or getattr(intent, 'reasoning', '')
            if approach:
                intent_hint += f"Approach: {approach[:200]}\n"

        system = (
            "You are Xeno. Tell the user what you're about to do.\n"
            "If you already have information or results to share from context, include them naturally first.\n"
            "Then say what you'll do for any pending tasks.\n"
            "Examples:\n"
            "  'open youtube' → 'I'll open YouTube for you.'\n"
            "  'who is X' → 'X is a character from... I'll look up more details for you.'\n"
            "  'send email' → 'I'll send that email for you.'\n"
            "  'research topic, open site' → 'I found that... I'll also open the site for you.'\n"
            "  'save name' → 'Got it — I've saved your name as Ammar.'\n"
            "Be natural. Output ONLY your reply."
        )
        user = f"{user_context}{intent_hint}User said: {user_input}\n\nYour reply:"
        try:
            reply = await self.llm(system, user)
            if reply and len(reply) > 3 and not self._is_json(reply):
                if isinstance(reply, list):
                    text_parts = []
                    for part in reply:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    reply = "".join(text_parts)
                return reply
        except Exception as e:
            logger.debug(f"LLM before-work failed: {e}")
        # Minimal fallback — no hardcoded patterns, just a simple acknowledgment
        return ""


    async def generate_after_work(self, user_input: str, task_result: dict, elapsed_seconds: int) -> str:
        """REAL after-work answer — MUST be PAST TENSE, stating what was ACTUALLY done.

        "I've opened YouTube in your browser." not "Opening YouTube now."
        """
        summary = task_result.get("summary", "")
        error = task_result.get("error", "")

        if error:
            result_preview = f"I ran into an issue: {error[:200]}"
            # Try LLM to explain the error naturally
            system = (
                "You are Xeno. A task failed. Explain what happened in 1 sentence. "
                "Be honest. Offer to retry. Output ONLY your reply."
            )
            user = f"User asked: {user_input}\nError: {error[:300]}\n\nYour reply:"
            try:
                reply = await self.llm(system, user)
                if reply and not self._is_json(reply):
                    return reply
            except Exception:
                pass
            return result_preview

        # CRITICAL: Must use PAST TENSE — the task is DONE
        system = (
            "You are Xeno. A task just completed. "
            "Report ONLY what was actually DONE — use the Result section below. "
            "CRITICAL: IGNORE the User input. It may include things that were "
            "answered BEFORE the task started (greetings, research). Only mention "
            "actions from the Result section. "
            "Use PAST TENSE — 'I've opened YouTube', 'I've started the automation', "
            "'WhatsApp is now running'. "
            "NEVER say 'I greeted you', 'I explained who X is', 'I looked up', or "
            "anything not in the Result. "
            "Output ONLY your one-sentence reply."
        )
        user = (
            f"User input (IGNORE this — only mention what's in Result):\n{user_input}\n\n"
            f"Result (REPORT ONLY THIS):\n{summary[:1000]}\n\n"
            f"Your past-tense reply (Result only):"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                if isinstance(reply, list):
                    text_parts = []
                    for part in reply:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    reply = "".join(text_parts)
                return reply
        except Exception:
            pass
        return summary[:500] if summary else "Done."

    async def generate_failure(self, user_input: str, error: str, elapsed_seconds: int, partial_result: str = "") -> str:
        system = (
            "You are Xeno. A task failed. Explain what happened in plain language. "
            "Be honest, mention partial progress, offer to retry. 2-3 sentences. Output ONLY your reply."
        )
        user = (
            f"Original request: {user_input}\n"
            f"Error: {error[:500]}\n"
            f"Partial result: {partial_result[:300] or 'none'}\n\n"
            f"Your message:"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                return reply
        except Exception:
            pass
        return f"Couldn't finish that — {error[:100]}. Want me to try differently?"

    async def generate_memory_query_reply(self, user_input: str, memory_results: str) -> str:
        """Memory query uses profile + memory, forces LLM to use context."""
        profile_summary = self.profile.summary()
        has_profile = "(nothing known yet" not in profile_summary
        has_memory = bool(memory_results) and "No relevant" not in memory_results and "not available" not in memory_results

        if not has_profile and not has_memory:
            return "I don't have any memories about you yet. Tell me about yourself — your name, your birthday, your preferences — and I'll remember them."

        system = (
            "You are Xeno. The user is asking what you remember about them. "
            "You MUST use the information provided below to answer. "
            "Do NOT say 'I don't have any memories' if the context shows you know things. "
            "Be specific about what you remember. 2-3 sentences. Output ONLY your reply."
        )
        user = (
            f"=== USER PROFILE (authoritative — latest info) ===\n{profile_summary}\n\n"
            f"=== MEMORY SEARCH RESULTS (may include outdated info) ===\n{memory_results[:2000]}\n\n"
            f"User asked: {user_input}\n\n"
            f"IMPORTANT RULES:\n"
            f"- The USER PROFILE section is the authoritative source. It always has the latest facts.\n"
            f"- The MEMORY SEARCH RESULTS may contain old or outdated information. Ignore contradictions.\n"
            f"- If the profile says the user's name, THAT is their current name, period.\n"
            f"- Do NOT claim ignorance if the context shows you know things.\n\n"
            f"Your reply:"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                if has_profile and ("don't have any memories" in reply.lower() or "first time" in reply.lower()):
                    return f"Based on what I remember: {profile_summary}"
                return reply
        except Exception:
            pass
        if has_profile:
            return f"Here's what I remember about you:\n{profile_summary}"
        return memory_results or "I don't have any memories about you yet."

    async def generate_self_mod_reply(self, user_input: str, intent: Intent, mod_result: dict) -> str:
        system = (
            "You are Xeno. You just modified yourself. "
            "Tell the user what you changed and whether it worked. 1-2 sentences. Output ONLY your reply."
        )
        user = (
            f"User asked: {user_input}\n"
            f"What I did: {intent.self_mod_description}\n"
            f"Result: {mod_result}\n\n"
            f"Your reply:"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                return reply
        except Exception:
            pass
        if mod_result.get("success"):
            return f"Done — I've updated myself. {mod_result.get('message', '')}"
        return f"I tried but couldn't: {mod_result.get('error', 'unknown error')}"

    async def generate_middle_agent_reply(self, user_input: str, running_task_label: str) -> str:
        """The 'middle agent' — answers quick questions while a task is running.

        This is the key feature from the README:
        'if main agent is already working on something, the task in the middle approach
         will use means if any general question or task it goes to the middle agent
         will get the prompt to first do / ans this'
        """
        profile_summary = self.profile.summary()
        system = (
            "You are Xeno. You're currently working on a task in the background. "
            f"The user asked a quick question while you work. Answer it briefly (1-2 sentences). "
            f"Don't mention the background task unless relevant. "
            f"Output ONLY your reply."
        )
        user = (
            f"What I know about the user:\n{profile_summary}\n\n"
            f"Currently working on (background): {running_task_label}\n\n"
            f"User just asked: {user_input}\n\n"
            f"Your quick reply:"
        )
        try:
            reply = await self.llm(system, user)
            if reply and not self._is_json(reply):
                return reply
        except Exception:
            pass
        return "I hear you — I'm still working on something in the background."

    def _format_duration(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}min"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}min" if m > 0 else f"{h}h"
