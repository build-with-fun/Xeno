"""Brain-Driven Orchestrator — the main conversation controller.

Implements the EXACT UX from the README:

1. BEFORE_WORK: Agent gives a REAL answer about what it's going to do
   "I'll open YouTube in your browser for you."

2. Task executes in the background (actually does the work)

3. AFTER_WORK: Agent tells the user what it ACTUALLY did
   "I've opened YouTube in your default browser. You should see it now."

4. MIDDLE AGENT: If the user asks a quick question while a task is running,
   a lightweight LLM call answers it without disrupting the main task.
   "if main agent is already working on something, the task in the middle
    approach will use means if any general question or task it goes to the
    middle agent will get the prompt to first do / ans this"

5. SCHEDULING: Reminders actually fire and display immediately.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from xeno.brain.response import ResponseGenerator
from xeno.auto.executor import AutoExecutor
from xeno.profile.manager import UserProfile

logger = logging.getLogger(__name__)


class BrainEventType(str, Enum):
    INSTANT_REPLY = "instant_reply"       # quick reply (chat, memory, etc.)
    BEFORE_WORK = "before_work"           # "I'll open YouTube for you."
    PROGRESS = "progress"                 # "Still working..."
    AFTER_WORK = "after_work"             # "I've opened YouTube. You should see it now."
    AFTER_FAILURE = "after_failure"       # "Couldn't finish that — <reason>"
    QUEUED = "queued"
    QUEUE_STARTED = "queue_started"
    SELF_MOD_RESULT = "self_mod_result"
    REMINDER = "reminder"                 # scheduled reminder fired
    INFO = "info"


@dataclass
class BrainEvent:
    type: BrainEventType
    message: str
    task_id: str = ""
    task_label: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class RunningTask:
    id: str
    label: str
    description: str
    started_at: float = field(default_factory=time.time)
    estimated_seconds: int = 60
    completed_steps: list[str] = field(default_factory=list)
    remaining_steps: list[str] = field(default_factory=list)
    task: Optional[asyncio.Task] = None
    result: Any = None
    error: str = ""
    status: str = "running"

    @property
    def elapsed_seconds(self) -> int:
        return int(time.time() - self.started_at)


class BrainOrchestrator:
    """The Main Agent orchestrator — routes everything through the deepagent.

    Flow:
    1. User sends message → BEFORE_WORK (real answer about what it'll do)
    2. Task runs in background via deepagent (all tools, sub-agents, skills)
    3. AFTER_WORK (real result of what was done)
    4. If user asks while task runs → middle agent answers quickly
    5. Scheduled reminders fire → REMINDER event displayed immediately

    No separate brain/intent analysis layer — the deepagent IS the brain.
    """

    def __init__(
        self,
        brain: Any,
        response_gen: ResponseGenerator,
        profile: UserProfile,
        auto_executor: AutoExecutor,
        task_runner: Optional[Callable[..., Awaitable[dict]]] = None,
        self_modifier: Optional[Any] = None,
        memory_recall_fn: Optional[Callable[[str], Awaitable[str]]] = None,
        web_search_fn: Optional[Callable[[str, int], Awaitable[str]]] = None,
        context_bridge: Optional[Any] = None,
        chat_store: Optional[Any] = None,
        temporal_kg: Optional[Any] = None,
        progress_check_interval: float = 30.0,
    ):
        self.brain = brain
        self.response_gen = response_gen
        self.profile = profile
        self.auto_executor = auto_executor
        self.task_runner = task_runner
        self.self_modifier = self_modifier
        self.memory_recall = memory_recall_fn
        self.web_search = web_search_fn
        self.context_bridge = context_bridge
        self.chat_store = chat_store
        self.temporal_kg = temporal_kg
        self.progress_interval = progress_check_interval

        self._running_tasks: dict[str, RunningTask] = {}
        self._queue: list[tuple[str, str, Any]] = []  # (task_id, user_input, intent)
        self._max_parallel: int = 999  # effectively unlimited parallel tasks
        self._compound_groups: dict[str, dict] = {}
        self._compound_before_emitted: dict[str, bool] = {}
        self._last_exec_result: dict = {}
        self._subscribers: list[asyncio.Queue[BrainEvent]] = []
        self._progress_task: Optional[asyncio.Task] = None
        self._started = False
        self._recent_reminders: list[dict] = []
        self._recent_schedules: list[dict] = []

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._progress_task = asyncio.create_task(self._progress_loop())
        logger.info("Brain orchestrator started")

    async def stop(self) -> None:
        self._started = False
        if self._progress_task:
            self._progress_task.cancel()
            try:
                await self._progress_task
            except asyncio.CancelledError:
                pass
        for rt in list(self._running_tasks.values()):
            if rt.task:
                rt.task.cancel()
        logger.info("Brain orchestrator stopped")

    def subscribe(self) -> asyncio.Queue[BrainEvent]:
        q: asyncio.Queue[BrainEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[BrainEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def _emit(self, event: BrainEvent) -> None:
        # Skip empty BEFORE_WORK messages (LLM failed to generate)
        if event.type == BrainEventType.BEFORE_WORK and not event.message:
            return
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping")

    @property
    def has_running_task(self) -> bool:
        return len(self._running_tasks) > 0

    @property
    def running_tasks_count(self) -> int:
        return sum(1 for t in self._running_tasks.values() if t.status == "running")

    @property
    def can_launch_more(self) -> bool:
        return self.running_tasks_count < self._max_parallel

    async def emit_reminder(self, name: str, prompt: str) -> None:
        """Called by the scheduler when a reminder fires. Displays immediately.

        The message is a NATURAL reminder, not robotic text.
        "Hey Ammar, time to go for a walk!" instead of "go for a walk: Remind the user to go for a walk now!"
        """
        self._recent_reminders.append({
            "name": name,
            "prompt": prompt,
            "fired_at": time.time(),
        })
        if len(self._recent_reminders) > 20:
            self._recent_reminders = self._recent_reminders[-20:]

        # Get user's name for personalization
        name_str = ""
        profile_summary = self.profile.summary()
        if "Name:" in profile_summary:
            for line in profile_summary.split("\n"):
                if line.startswith("Name:"):
                    name_str = line.replace("Name:", "").strip()
                    break

        # Build a natural reminder message
        # Remove robotic prefixes from the prompt
        clean_prompt = prompt
        for prefix in ["Remind the user to ", "Remind me to ", "Remind the user ", "Remind me "]:
            if clean_prompt.lower().startswith(prefix.lower()):
                clean_prompt = clean_prompt[len(prefix):]
                break
        # Capitalize first letter
        if clean_prompt:
            clean_prompt = clean_prompt[0].upper() + clean_prompt[1:]

        # Build the message
        if name_str:
            message = f"Hey {name_str}, it's time to {clean_prompt.lower()}"
        else:
            message = f"It's time to {clean_prompt.lower()}"
        # Remove trailing period if present
        message = message.rstrip(".")

        await self._emit(BrainEvent(
            type=BrainEventType.REMINDER,
            message=message,
            metadata={"reminder": True, "name": name, "prompt": prompt},
        ))

    # Stop/cancel keywords — checked BEFORE brain analysis for instant response
    STOP_KEYWORDS = {
        "stop", "stop it", "stop that", "stop working",
        "stop the task", "stop the agent",
        "cancel", "cancel it", "cancel all", "cancel all tasks",
        "abort", "kill it", "kill", "kill all",
        "nevermind", "never mind",
        "halt", "shut up", "enough", "quit that", "quit",
    }

    # Intents that answer instantly without BEFORE_WORK (small talk, emotional)
    INSTANT_INTENTS = {
        "quick_reply", "emotional",
    }

    # Intents that do work FIRST, then emit the result as BEFORE_WORK (no AFTER_WORK).
    # quick_research → do web search, show answer in BEFORE_WORK
    # memory_query → recall memory, show result in BEFORE_WORK
    # memory_store/memory_update/memory_delete → done by auto-executor, show confirmation in BEFORE_WORK
    DIRECT_INTENTS = {
        "memory_query", "memory_store", "memory_delete", "memory_update",
        "quick_research",
    }

    # Intents that MUST go through deepagent (user explicitly asked for research/deep research)
    DEEPAGENT_INTENTS = {
        "research", "deep_research",
    }

    # Middle agent — only intercept short chat/greetings, let everything else through
    _MIDDLE_AGENT_KEYWORDS = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "how are you", "how's it going", "good morning", "good evening",
        "yo", "sup", "what's up", "wyd", "status", "how r u",
        "bye", "goodbye", "see ya", "later",
    }
    _MIDDLE_AGENT_MAX_WORDS = 6

    async def handle_user_input(self, user_input: str) -> None:
        """Main entry point — the MAIN AGENT handles everything directly.

        The brain/intent analysis runs as an OPTIONAL enrichment layer for fact
        extraction. The deepagent (Main Agent) handles ALL actual execution —
        simple Q&A, tool calls, compound tasks — natively.
        BEFORE_WORK gives instant feedback, task runs in background, AFTER_WORK shows result.

        If a task is already running, the MIDDLE AGENT intercepts quick questions
        without disrupting the main task.
        """
        # 0. INSTANT STOP/CANCEL CHECK — no LLM call needed
        user_lower = user_input.lower().strip()
        if not user_lower:
            return
        if user_lower in self.STOP_KEYWORDS:
            await self._cancel_running_task(user_input)
            return

        # 0a. MIDDLE AGENT — only intercept short chat/greetings while tasks run.
        #     New task requests (anything longer or complex) fall through to brain.
        if self.has_running_task:
            word_count = len(user_lower.split())
            is_short_chat = (
                word_count <= self._MIDDLE_AGENT_MAX_WORDS
                and (
                    user_lower in self._MIDDLE_AGENT_KEYWORDS
                    or any(user_lower.startswith(k) for k in self._MIDDLE_AGENT_KEYWORDS)
                )
            )
            if is_short_chat:
                try:
                    running_labels = [t.label for t in self._running_tasks.values() if t.status == "running"]
                    if running_labels:
                        middle_reply = await self.response_gen.generate_middle_agent_reply(
                            user_input, running_labels[0]
                        )
                        await self._emit(BrainEvent(
                            type=BrainEventType.INSTANT_REPLY,
                            message=middle_reply,
                            metadata={"via": "middle_agent", "running_task": running_labels[0]},
                        ))
                        return
                except Exception as e:
                    logger.debug(f"Middle agent failed (non-critical): {e}")
                    # Fall through to normal processing

        # 0a. Persist user input to ChatStore
        if self.chat_store:
            try:
                sessions = self.chat_store.list_sessions()
                if sessions:
                    await self.chat_store.add_message(sessions[-1]['id'], "user", user_input[:1000])
            except Exception:
                pass

        # 0b. Record user fact in TemporalKG
        if self.temporal_kg:
            try:
                self.temporal_kg.add_fact("user_input", "latest", user_input[:200],
                    source="user", metadata={"timestamp": time.time()})
            except Exception:
                pass

        # 0c. Build profile context
        profile_summary = self.profile.summary()
        try:
            from xeno.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                all_sched = sched.list_all()
                if all_sched and "No schedules" not in all_sched:
                    profile_summary += f"\nActive schedules:\n{all_sched[:600]}"
        except Exception:
            pass
        # Append contact context (WhatsApp + Gmail) so the brain/agent knows who's in the user's network
        try:
            from xeno.contacts import get_contact_context
            contact_ctx = get_contact_context()
            if contact_ctx:
                profile_summary += f"\n\n## Contact Network\n{contact_ctx[:1500]}"
        except Exception:
            pass

        # 1. Brain analysis — OPTIONAL, best-effort fact extraction
        intent = None
        try:
            intent = await self.brain.analyze(
                user_input=user_input,
                user_profile_summary=profile_summary,
            )
            logger.info(f"Brain intent: {intent.intent_type.value} (conf={intent.confidence:.2f}) — {intent.reasoning[:80] if intent.reasoning else ''}")
        except Exception as e:
            logger.debug(f"Brain analysis failed (non-critical): {e}")

        # 2. Extract facts/schedules from brain output if valid JSON was returned
        self._last_exec_result = {}
        if intent and hasattr(intent, 'facts') and intent.facts:
            try:
                exec_result = await self.auto_executor.execute(intent)
                self._last_exec_result = exec_result
                for sched in exec_result.get("schedules_created", []):
                    self._recent_schedules.append({
                        "name": sched["name"],
                        "schedule_type": sched["schedule_type"],
                        "created_at": time.time(),
                    })
                    if len(self._recent_schedules) > 20:
                        self._recent_schedules = self._recent_schedules[-20:]
            except Exception as e:
                logger.debug(f"Auto-executor failed (non-critical): {e}")

        # 3. Memory recall for context
        memory_context = ""
        if self.memory_recall is not None:
            try:
                memory_context = await self.memory_recall(user_input)
            except Exception:
                pass

        # 4. Use brain intent to decide routing
        intent_type = getattr(intent, 'intent_type', None)
        intent_str = intent_type.value if intent_type else ""

        # Check for compound query with sub_intents
        sub_intents = getattr(intent, 'sub_intents', None) or []
        if sub_intents:
            await self._handle_compound_query(user_input, sub_intents, profile_summary)
            return

        if intent_str in self.INSTANT_INTENTS:
            # Answer instantly without BEFORE_WORK — small talk, emotional support
            reply = await self.response_gen.generate_quick_reply(user_input, intent, extra_context=profile_summary)
            await self._emit(BrainEvent(
                type=BrainEventType.INSTANT_REPLY,
                message=reply,
            ))
            return

        if intent_str in self.DIRECT_INTENTS:
            # Do the actual work FIRST, then emit result as BEFORE_WORK (no AFTER_WORK needed)
            if intent_str == "quick_research":
                reply = await self._quick_web_search(user_input)
            elif intent_str == "memory_query":
                reply = await self.response_gen.generate_memory_query_reply(user_input, memory_context)
            elif intent_str == "memory_store":
                reply = await self.response_gen.generate_memory_store_reply(
                    user_input, intent,
                    self._last_exec_result or {"facts_stored": [], "schedules_created": []},
                )
            elif intent_str in ("memory_delete", "memory_update"):
                reply = await self.response_gen.generate_memory_query_reply(user_input, memory_context)
            else:
                reply = ""
            await self._emit(BrainEvent(
                type=BrainEventType.BEFORE_WORK,
                task_id=f"direct_{uuid.uuid4().hex[:8]}",
                task_label=user_input[:60],
                message=reply,
            ))
            return

        # 5. Generate BEFORE_WORK — LLM says what it'll do before routing to deepagent
        before_msg = await self.response_gen.generate_before_work(
            user_input, intent, memory_context,
            extra_context=profile_summary,
        )

        # 6. Route to deepagent with BEFORE_WORK/AFTER_WORK wrapping
        await self._start_task_background(user_input, intent, before_msg)

    async def _handle_compound_query(self, original_input: str, sub_intents: list, profile_summary: str) -> None:
        """Split a compound query: direct intents are DONE FIRST and their results
        embedded in the combined BEFORE_WORK. Tasks run in background with
        suppressed BEFORE_WORK. All task results collected into one combined AFTER_WORK.
        No separate AFTER_WORK for direct intents — answers shown in BEFORE_WORK."""
        direct_intents = []
        task_subintents = []

        for si in sub_intents:
            si_str = getattr(getattr(si, 'intent_type', None), 'value', '')
            if si_str in self.INSTANT_INTENTS:
                pass  # greeting handled naturally by BEFORE_WORK
            elif si_str in self.DIRECT_INTENTS:
                direct_intents.append(si)
            else:
                task_subintents.append(si)

        # Process all direct intents FIRST — do the actual work
        direct_results = []
        for si in direct_intents:
            si_str = getattr(getattr(si, 'intent_type', None), 'value', '')
            desc = getattr(si, 'task_approach', '') or getattr(si, 'reasoning', '') or getattr(si, 'draft_response', original_input)
            if si_str == "quick_research":
                result = await self._quick_web_search(
                    getattr(si, 'draft_response', '') or getattr(si, 'reasoning', original_input),
                )
            elif si_str == "memory_query":
                result = await self.response_gen.generate_memory_query_reply(
                    getattr(si, 'draft_response', '') or getattr(si, 'reasoning', original_input),
                    self.memory_recall and await self.memory_recall(desc) or "",
                )
            elif si_str == "memory_store":
                result = await self.response_gen.generate_memory_store_reply(
                    getattr(si, 'draft_response', '') or getattr(si, 'reasoning', original_input),
                    si, self._last_exec_result or {"facts_stored": [], "schedules_created": []},
                )
            else:
                result = await self.response_gen.generate_memory_query_reply(
                    getattr(si, 'draft_response', '') or getattr(si, 'reasoning', original_input),
                    self.memory_recall and await self.memory_recall(desc) or "",
                )
            direct_results.append(result)

        # Build extra context with pre-computed results + pending tasks
        extra_parts = []
        if direct_results:
            extras = "\n".join(f"- {r[:400]}" for r in direct_results)
            extra_parts.append(f"Results already available (share these with the user):\n{extras}")
        if task_subintents:
            task_descs = []
            for si in task_subintents:
                desc = getattr(si, 'task_approach', '') or getattr(si, 'reasoning', '') or getattr(si, 'draft_response', original_input)
                if not desc or desc == original_input:
                    desc = getattr(si, 'draft_response', '') or original_input
                task_descs.append(desc)
            pending = "\n".join(f"- {d[:200]}" for d in task_descs)
            extra_parts.append(f"Pending tasks (say what you'll do for these):\n{pending}")
        extra_ctx = "\n\n".join(extra_parts) if extra_parts else ""

        # Generate ONE BEFORE_WORK that includes pre-computed results + pending tasks
        combined_before = await self.response_gen.generate_before_work(
            original_input, None, extra_context=f"{profile_summary}\n\n{extra_ctx}" if extra_ctx else profile_summary,
        )
        cmp_label = original_input[:60]
        await self._emit(BrainEvent(
            type=BrainEventType.BEFORE_WORK,
            task_id=f"cmp_{uuid.uuid4().hex[:8]}",
            task_label=cmp_label,
            message=combined_before,
        ))

        if not task_subintents:
            return

        # Create a compound group to track all subtasks for combined AFTER_WORK
        compound_id = f"cmp_{uuid.uuid4().hex[:8]}"
        self._compound_groups[compound_id] = {
            "original_input": original_input,
            "remaining": len(task_subintents),
            "results": [],
        }
        self._compound_before_emitted[compound_id] = True  # suppress individual BEFORE_WORK

        # Launch each sub-intent as a separate parallel task (BEFORE_WORK already shown)
        for si in task_subintents:
            desc = getattr(si, 'task_approach', '') or getattr(si, 'reasoning', original_input)
            if not desc or desc == original_input:
                desc = getattr(si, 'draft_response', '') or original_input
            await self._start_task_background(desc, si, None, compound_id=compound_id)

    async def _quick_web_search(self, query: str) -> str:
        """Quick web search — used for quick_research intents (no deepagent needed).
        Uses ddgs directly (same engine the deepagent's web_search tool uses)."""
        try:
            from ddgs import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    title = r.get("title", "")
                    snippet = r.get("body", "")
                    url = r.get("href", "")
                    results.append(f"• {title}\n  {snippet[:200]}\n  {url}")
            output = "\n\n".join(results) if results else f"I searched for '{query}' but didn't find much."
            return output[:2000]
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=5):
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        url = r.get("href", "")
                        results.append(f"• {title}\n  {snippet[:200]}\n  {url}")
                output = "\n\n".join(results) if results else f"I searched for '{query}' but didn't find much."
                return output[:2000]
            except ImportError:
                return "Web search unavailable. Install: pip install ddgs"
        except Exception as e:
            return f"Search failed: {e}"

    async def _start_task_background(self, user_input: str, intent: Any = None, before_msg: str = None, compound_id: str = "") -> None:
        """Start a task in the BACKGROUND — fire and forget, parallel support.

        BEFORE_WORK is shown immediately, then control returns to the user.
        The task runs asynchronously. When it completes, AFTER_WORK is emitted.

        If compound_id is set, the task is part of a compound group. Results
        are collected and a single combined AFTER_WORK is generated when all
        tasks in the group complete.

        If max parallel tasks are already running, this one gets queued.
        Up to `_max_parallel` (default 3) tasks run simultaneously.
        """
        if self.task_runner is None:
            await self._emit(BrainEvent(
                type=BrainEventType.INFO,
                message="I'd start a task for this, but no task runner is configured.",
            ))
            return

        # If max parallel tasks reached, queue this one
        if not self.can_launch_more:
            await self._queue_task(user_input, intent)
            return

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task_label = user_input[:60] + ("..." if len(user_input) > 60 else "")

        # BEFORE_WORK: use provided message or generate one
        # Suppress if compound group already showed the combined BEFORE_WORK
        skip_bw = compound_id and self._compound_before_emitted.get(compound_id)
        if not skip_bw:
            if before_msg is None:
                before_msg = await self.response_gen.generate_before_work(user_input, intent)
            await self._emit(BrainEvent(
                type=BrainEventType.BEFORE_WORK,
                message=before_msg,
                task_id=task_id,
                task_label=task_label,
                metadata={
                    "estimated_seconds": 30,
                },
            ))


        # Create the running task tracker
        running = RunningTask(
            id=task_id,
            label=task_label,
            description=user_input,
            estimated_seconds=30,
        )
        self._running_tasks[task_id] = running

        # FIRE AND FORGET — task runs in background, control returns immediately
        running.task = asyncio.create_task(self._run_task(running, task_id, intent, compound_id))

    async def _cancel_running_task(self, user_input: str) -> None:
        """Cancel all running background tasks immediately.

        Called when the user says 'stop', 'cancel', 'abort', etc.
        """
        cancelled_count = 0

        for tid, rt in list(self._running_tasks.items()):
            if rt.task:
                rt.task.cancel()
                rt.status = "cancelled"
                cancelled_count += 1
                logger.info(f"Task '{rt.label}' cancelled by user")

        queue_count = len(self._queue)
        self._queue.clear()
        cancelled_count += queue_count

        if cancelled_count > 0:
            msg = f"Stopped. Cancelled {cancelled_count} task(s)."
            if queue_count > 0 and cancelled_count > 1:
                msg += f" ({cancelled_count - queue_count} running + {queue_count} queued)"
        else:
            msg = "Nothing is running right now — nothing to stop."

        await self._emit(BrainEvent(
            type=BrainEventType.INFO,
            message=msg,
            metadata={"cancelled": cancelled_count},
        ))

    async def _run_task(self, running: RunningTask, task_id: str, intent: Any = None, compound_id: str = "") -> None:
        """Run a background task to completion with SELF-HEALING.

        If the task fails, the agent:
        1. Diagnoses the error (missing module? broken code? wrong API key?)
        2. Attempts to fix it (install module, fix code, etc.)
        3. Retries the task (up to 2 retries)
        4. If all retries fail, reports the error to the user
        """
        max_retries = 2  # self-healing retries
        last_error = None

        try:
            for attempt in range(max_retries + 1):
                try:
                    running = self._running_tasks.get(task_id)
                    if running is None:
                        return
                    logger.info(f"Task {running.id} starting (attempt {attempt+1}): {running.description[:80]}")
                    result = await self.task_runner(running.id, running.description, intent)
                    running.result = result
                    running.status = "done"
                    logger.info(f"Task {running.id} completed: {str(result)[:100]}")

                    # Record result in ChatStore and TemporalKG
                    if self.chat_store:
                        try:
                            sessions = self.chat_store.list_sessions()
                            if sessions:
                                summary = result.get("summary", "")[:500] if isinstance(result, dict) else str(result)[:500]
                                self.chat_store.add_message(sessions[-1].session_id, "assistant", summary)
                        except Exception:
                            pass
                    if self.temporal_kg:
                        try:
                            self.temporal_kg.add_fact("task", running.id,
                                str(running.description)[:200], source="agent",
                                metadata={"elapsed": running.elapsed_seconds, "success": True})
                        except Exception:
                            pass

                    # AFTER_WORK: Check if this task is part of a compound group
                    if compound_id and compound_id in self._compound_groups:
                        group = self._compound_groups[compound_id]
                        group["results"].append({
                            "task": running.description,
                            "summary": result.get("summary", "") if isinstance(result, dict) else str(result),
                        })
                        group["remaining"] -= 1
                        if group["remaining"] > 0:
                            return  # wait for other tasks to complete
                        # All tasks done — generate combined AFTER_WORK
                        combined_summary = "\n".join(
                            f"- {r['task']}: {r['summary'][:200]}"
                            for r in group["results"]
                        )
                        combined_result = {
                            "summary": combined_summary,
                            "artifacts": [],
                        }
                        # Only pass task descriptions (not the original compound input)
                        # so AFTER_WORK doesn't mention greetings/research that were in BEFORE_WORK
                        task_only_input = "; ".join(f"{r['task']}" for r in group["results"])
                        after_msg = await self.response_gen.generate_after_work(
                            user_input=task_only_input or group["original_input"],
                            task_result=combined_result,
                            elapsed_seconds=running.elapsed_seconds,
                        )
                        self._compound_groups.pop(compound_id, None)
                    else:
                        after_msg = await self.response_gen.generate_after_work(
                            user_input=running.description,
                            task_result=result,
                            elapsed_seconds=running.elapsed_seconds,
                        )

                    await self._emit(BrainEvent(
                        type=BrainEventType.AFTER_WORK,
                        message=after_msg,
                        task_id=running.id,
                        task_label=running.label,
                        metadata={
                            "summary": result.get("summary", "") if isinstance(result, dict) else str(result),
                            "artifacts": result.get("artifacts", []) if isinstance(result, dict) else [],
                            "elapsed_seconds": running.elapsed_seconds,
                            "attempts": attempt + 1,
                        },
                    ))
                    return  # success — exit

                except asyncio.CancelledError:
                    running = self._running_tasks.get(task_id)
                    if running:
                        running.status = "cancelled"
                        await self._emit(BrainEvent(
                            type=BrainEventType.INFO,
                            message=f"Task '{running.label}' was cancelled.",
                            task_id=running.id,
                        ))
                    raise

                except Exception as e:
                    running = self._running_tasks.get(task_id)
                    last_error = e
                    logger.warning(f"Task {task_id} attempt {attempt+1} failed: {e}")

                    if running and attempt < max_retries:
                        # SELF-HEALING: diagnose and fix
                        await self._emit(BrainEvent(
                            type=BrainEventType.INFO,
                            message=f"Something went wrong — diagnosing and attempting to fix automatically...",
                            task_id=running.id,
                        ))

                        healed = await self._self_heal(str(e), running.description)
                        if healed:
                            logger.info(f"Task {running.id}: self-healing successful, retrying...")
                            await self._emit(BrainEvent(
                                type=BrainEventType.INFO,
                                message=f"Fixed the issue automatically. Retrying...",
                                task_id=running.id,
                            ))
                            continue  # retry
                        else:
                            logger.warning(f"Task {running.id}: self-healing couldn't fix the issue")
                            break  # can't fix — report failure
                    else:
                        break  # out of retries

            # All retries exhausted — report failure
            running = self._running_tasks.get(task_id)
            if running:
                running.status = "failed"
                running.error = str(last_error)

                failure_msg = await self.response_gen.generate_failure(
                    user_input=running.description,
                    error=str(last_error),
                    elapsed_seconds=running.elapsed_seconds,
                    partial_result=str(running.result) if running.result else "",
                )
                await self._emit(BrainEvent(
                    type=BrainEventType.AFTER_FAILURE,
                    message=failure_msg,
                    task_id=running.id,
                    task_label=running.label,
                    metadata={"error": str(last_error), "attempts": max_retries + 1},
                ))

        finally:
            # CRITICAL: always clean up and drain queued tasks while slots available
            self._running_tasks.pop(task_id, None)
            while self._queue and self.can_launch_more:
                await self._start_next_queued()

    async def _load_failure_patterns(self):
        if not hasattr(self, '_failure_patterns'):
            self._failure_patterns_path = Path("data/failure_patterns.json")
            self._failure_patterns = {}
        if self._failure_patterns_path.exists():
            try:
                self._failure_patterns = json.loads(self._failure_patterns_path.read_text(encoding="utf-8"))
            except Exception:
                self._failure_patterns = {}

    async def _save_failure_pattern(self, error_type: str, error_snippet: str, fix_action: str, success: bool):
        key = error_type[:60]
        if key not in self._failure_patterns:
            self._failure_patterns[key] = {"count": 0, "success_count": 0, "last_fix": "", "examples": []}
        p = self._failure_patterns[key]
        p["count"] += 1
        if success:
            p["success_count"] += 1
        p["last_fix"] = fix_action
        p["examples"].append({"snippet": error_snippet[:100], "fix": fix_action, "success": success})
        if len(p["examples"]) > 10:
            p["examples"] = p["examples"][-10:]
        try:
            self._failure_patterns_path.parent.mkdir(parents=True, exist_ok=True)
            self._failure_patterns_path.write_text(json.dumps(self._failure_patterns, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _classify_error(self, error: str) -> tuple[str, str]:
        """Classify error into (type, extract) for pattern matching."""
        el = error.lower()
        mod_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error)
        if mod_match:
            return ("missing_module", mod_match.group(1))
        if "syntaxerror" in el:
            return ("syntax_error", error[:120])
        if "nameerror" in el or "is not defined" in el:
            return ("name_error", error[:200])
        if "importerror" in el:
            return ("import_error", error[:120])
        if any(kw in el for kw in ["api key", "api_key", "401", "403", "unauthorized", "forbidden"]):
            return ("auth_error", error[:100])
        if any(kw in el for kw in ["connectionerror", "connection refused", "timeout"]):
            return ("network_error", error[:100])
        if "filenotfounderror" in el or "file not found" in el:
            return ("file_not_found", error[:120])
        if "permission" in el:
            return ("permission_error", error[:120])
        if "json.decoder.jsondecodeerror" in el or "jsondecodeerror" in el:
            return ("json_parse_error", error[:120])
        if "keyerror" in el:
            return ("key_error", error[:120])
        return ("generic", error[:200])

    async def _self_heal(self, error: str, context: str) -> bool:
        """SELF-HEALING 2.0: multi-strategy recovery with failure pattern learning.

        Classifies errors → tries known fix patterns → learns from success/failure.
        """
        await self._load_failure_patterns()
        error_type, error_extract = self._classify_error(error)
        logger.info(f"Self-heal: classified '{error_type}': {error_extract[:80]}")

        # Check if we've seen this pattern before
        known_fix = self._failure_patterns.get(error_type, {}).get("last_fix", "")
        if known_fix and self._failure_patterns.get(error_type, {}).get("success_count", 0) > 0:
            logger.info(f"Self-heal: known pattern '{error_type}', last fix: {known_fix[:60]}")

        # Strategy 1: Missing module → pip install
        if error_type == "missing_module":
            module = error_extract
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", module],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    await self._save_failure_pattern(error_type, error, f"pip install {module}", True)
                    return True
                pip_names = {"PIL": "Pillow", "bs4": "beautifulsoup4", "yaml": "pyyaml", "sklearn": "scikit-learn", "cv2": "opencv-python"}
                pip_name = pip_names.get(module, module)
                if pip_name != module:
                    result = subprocess.run([sys.executable, "-m", "pip", "install", pip_name], capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        await self._save_failure_pattern(error_type, error, f"pip install {pip_name}", True)
                        return True
            except Exception as e:
                logger.warning(f"Self-heal: pip install failed: {e}")
            await self._save_failure_pattern(error_type, error, "pip install failed", False)
            return False

        # Strategy 2: Syntax/Import errors → LLM fix
        if error_type in ("syntax_error", "import_error"):
            file_match = re.search(r'File "([^"]+)", line (\d+)', error)
            if file_match and self.self_modifier is not None:
                try:
                    result = await self.self_modifier.fix_error(error=error, traceback_str=error, context=context)
                    if result.success:
                        await self._save_failure_pattern(error_type, error, f"LLM fix: {file_match.group(1)}", True)
                        return True
                except Exception:
                    pass
            await self._save_failure_pattern(error_type, error, "LLM fix failed", False)
            return False

        # Strategy 3: Auth/API key → can't auto-fix
        if error_type == "auth_error":
            logger.info("Self-heal: API key error — can't auto-fix")
            return False

        # Strategy 4: Network → can't auto-fix
        if error_type == "network_error":
            logger.info("Self-heal: connection error — can't auto-fix")
            return False

        # Strategy 5: File not found → create empty parent dirs
        if error_type == "file_not_found":
            file_match = re.search(r"'([^']+)'", error)
            if file_match:
                try:
                    Path(file_match.group(1)).parent.mkdir(parents=True, exist_ok=True)
                    await self._save_failure_pattern(error_type, error, "created parent dirs", True)
                    return True
                except Exception:
                    pass

        # Strategy 6: JSON parse → suggest fix
        if error_type == "json_parse_error":
            logger.info("Self-heal: JSON parse error — try fixing the JSON structure")
            return False

        # Strategy 7: NameError → try LLM fix with file extraction
        if error_type == "name_error":
            file_match = re.search(r'File "([^"]+)", line (\d+)', error)
            if file_match and self.self_modifier is not None:
                try:
                    result = await self.self_modifier.fix_error(error=error, traceback_str=error, context=context)
                    if result.success:
                        await self._save_failure_pattern(error_type, error, f"LLM fixed {file_match.group(1)}", True)
                        return True
                except Exception:
                    pass
            # If no file info or fix failed, try to suggest the actual fix
            var_match = re.search(r"name '(\w+)' is not defined", error)
            if var_match:
                var_name = var_match.group(1)
                logger.info(f"Self-heal: name_error — undefined variable '{var_name}'. Check scope/imports.")
            await self._save_failure_pattern(error_type, error, "LLM fix failed", False)
            return False

        # Strategy 8: Generic → try LLM
        if self.self_modifier is not None:
            try:
                result = await self.self_modifier.fix_error(error=error, traceback_str=error, context=context)
                if result.success:
                    await self._save_failure_pattern(error_type, error, "LLM generic fix", True)
                    return True
            except Exception:
                pass

        logger.info(f"Self-heal: no fix for '{error_type}'")
        await self._save_failure_pattern(error_type, error, "no fix found", False)
        return False

    async def _queue_task(self, user_input: str, intent: Any = None) -> None:
        task_id = f"queued_{uuid.uuid4().hex[:8]}"
        self._queue.append((task_id, user_input, intent))
        await self._emit(BrainEvent(
            type=BrainEventType.QUEUED,
            message=f"Got it — I'll do '{user_input[:50]}...' after the current task finishes. (Position {len(self._queue)})",
            task_id=task_id,
        ))

    async def _start_next_queued(self) -> None:
        if not self._queue:
            return
        if not self.can_launch_more:
            return
        task_id, user_input, queued_intent = self._queue.pop(0)
        await self._emit(BrainEvent(
            type=BrainEventType.QUEUE_STARTED,
            message=f"Now starting: '{user_input[:50]}...'",
            task_id=task_id,
        ))
        await self._start_task_background(user_input, intent=queued_intent)

    async def _progress_loop(self) -> None:
        while self._started:
            try:
                await asyncio.sleep(self.progress_interval)
                if not self.has_running_task:
                    continue
                for tid, running in list(self._running_tasks.items()):
                    if running.elapsed_seconds < self.progress_interval:
                        continue
                    await self._emit(BrainEvent(
                        type=BrainEventType.PROGRESS,
                        message=f"Still working on {running.label} — {running.elapsed_seconds}s elapsed...",
                        task_id=tid,
                    ))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Progress loop error: {e}")

    def status(self) -> dict:
        return {
            "started": self._started,
            "running_tasks": [
                {"id": t.id, "label": t.label, "status": t.status, "elapsed": t.elapsed_seconds}
                for t in self._running_tasks.values()
            ],
            "running_count": len(self._running_tasks),
            "max_parallel": self._max_parallel,
            "compound_groups": len(self._compound_groups),
            "queue_size": len(self._queue),
            "profile_stats": self.profile.stats(),
            "recent_reminders": len(self._recent_reminders),
            "recent_schedules": len(self._recent_schedules),
        }
