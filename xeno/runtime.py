"""Xeno 2.0 Runtime — wires all 13+ phases together.

Enhanced with:
- Hermes-style prompt architecture (SOUL.md + layered prompts + prompt caching)
- Agent-native computer use (CDP bridge + structured state reader + action planner)
- Multi-agent orchestration patterns (supervisor, pipeline, fanout, debate, adaptive)
- Observability (tracing, metrics, exporters)
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from xeno.config import XenoConfig

# Phase 1
from xeno.harness import (
    FeatureListManager, ProgressTracker, GitCheckpointer,
    HarnessLoop, HarnessInitializer, SessionContext,
)
# Phase 2
from xeno.memory.unified import UnifiedMemoryManager
# Phase 3
from xeno.subagents.isolated import SubAgentOrchestrator
# Phase 4
from xeno.plan import PlanManager, ModeController, AutoCompactor
# Phase 5
from xeno.hooks import HookRegistry, RiskClassifier, AuditLog
from xeno.hooks.governance import register_governance_hooks
# Phase 6
from xeno.sandbox import PersistentSandboxPool
# Phase 7
from xeno.tui import make_tui, RichTUI
# Phase 8
from xeno.proactive import EventBus, DaemonManager, FileWatcherDaemon, MemoryDaemon
# Phase 9
from xeno.protocols import MCP2025Client, A2AClient, A2AAgentCard, AGNTCYClient, UMPAccessController
from xeno.context_bridge import AgentContextBridge
# Phase 10
from xeno.self_improve import SkillMiner, ABTestRunner, EvalSuite
# Phase 11
from xeno.production import ProductionBundle
# Phase 12 (legacy)
from xeno.middle import InputClassifier, TaskAcknowledger, MiddleAgent, ConversationalOrchestrator
# Phase 13
from xeno.brain import Brain, ResponseGenerator, BrainOrchestrator
from xeno.profile import UserProfile
from xeno.auto import AutoExecutor
from xeno.self_mod import SelfModifier

# Phase 14: Prompt Architecture (Hermes-style)
from xeno.prompt import PromptBuilder, PromptTierBuilder, ContextCompressor

# Phase 15: Agent-Native Computer Use
from xeno.computer_use import CDPBridge, StateReader, ActionPlanner

# Phase 16: Multi-Agent Orchestration
from xeno.orchestration import (
    SupervisorOrchestrator, PipelineOrchestrator,
    FanOutOrchestrator, DebateOrchestrator, AdaptiveOrchestrator,
)

# Phase 17: Observability
from xeno.observability import Tracer, MetricsCollector, get_tracer, get_metrics
from xeno.observability.exporter import ConsoleExporter, FileExporter

logger = logging.getLogger(__name__)


@dataclass
class XenoRuntime:
    config: XenoConfig

    # Phase 1
    feature_list: Optional[FeatureListManager] = None
    progress: Optional[ProgressTracker] = None
    checkpointer: Optional[GitCheckpointer] = None
    harness_loop: Optional[HarnessLoop] = None
    initializer: Optional[HarnessInitializer] = None

    # Phase 2
    memory: Optional[UnifiedMemoryManager] = None

    # Phase 3
    subagents: Optional[SubAgentOrchestrator] = None

    # Phase 4
    plans: Optional[PlanManager] = None
    modes: Optional[ModeController] = None
    compactor: Optional[AutoCompactor] = None

    # Phase 5
    hooks: Optional[HookRegistry] = None
    risk: Optional[RiskClassifier] = None
    audit: Optional[AuditLog] = None

    # Phase 6
    sandbox_pool: Optional[PersistentSandboxPool] = None

    # Phase 7
    tui: Optional[RichTUI] = None

    # Phase 8
    event_bus: Optional[EventBus] = None
    daemons: Optional[DaemonManager] = None

    # Phase 9
    mcp_2025: Optional[MCP2025Client] = None
    a2a: Optional[A2AClient] = None
    agntcy: Optional[AGNTCYClient] = None
    ump_server: Optional[UMPAccessController] = None

    # Phase 10
    skill_miner: Optional[SkillMiner] = None
    ab_tester: Optional[ABTestRunner] = None
    eval_suite: Optional[EvalSuite] = None

    # Phase 11
    production: Optional[ProductionBundle] = None

    # Phase 12 (legacy)
    conversation: Optional[ConversationalOrchestrator] = None

    # Phase 13
    brain: Optional[Brain] = None
    response_gen: Optional[ResponseGenerator] = None
    profile: Optional[UserProfile] = None
    auto_executor: Optional[AutoExecutor] = None
    self_modifier: Optional[SelfModifier] = None
    brain_orchestrator: Optional[BrainOrchestrator] = None

    # Context Bridge (24/7 agent activity)
    context_bridge: Optional[AgentContextBridge] = None

    # Phase 14: Prompt Architecture
    prompt_builder: Optional[PromptBuilder] = None
    prompt_tiers: Optional[PromptTierBuilder] = None
    context_compressor: Optional[ContextCompressor] = None

    # Phase 15: Computer Use
    cdp_bridge: Optional[CDPBridge] = None
    state_reader: Optional[StateReader] = None
    action_planner: Optional[ActionPlanner] = None

    # Phase 16: Multi-Agent Orchestration
    supervisor: Optional[SupervisorOrchestrator] = None
    pipeline: Optional[PipelineOrchestrator] = None
    fanout: Optional[FanOutOrchestrator] = None
    debate: Optional[DebateOrchestrator] = None
    adaptive: Optional[AdaptiveOrchestrator] = None

    # Phase 17: Observability
    tracer: Optional[Tracer] = None
    metrics: Optional[MetricsCollector] = None

    # ── XenoAtlas Subsystems ──────────────────────────────────────────────
    agent_pool: Any = None
    chat_store: Any = None
    always_on_manager: Any = None
    security_gateway: Any = None
    skill_synthesiser: Any = None
    temporal_kg: Any = None
    mcp_lifecycle: Any = None

    # State
    session_id: str = ""
    started: bool = False
    startup_context: Optional[SessionContext] = None
    llm: Any = None
    _scheduler_task: Optional[asyncio.Task] = None
    notify_callback: Optional[Callable[[str], None]] = None

    async def startup(self, llm: Any = None) -> SessionContext:
        if self.started:
            return self.startup_context or SessionContext()

        self.llm = llm
        self.session_id = f"sess_{int(asyncio.get_event_loop().time() * 1000)}"
        logger.info(f"Starting Xeno 2.0 runtime (session={self.session_id})")

        # === Phase 1: Harness ===
        self.feature_list = FeatureListManager(self.config.data_dir)
        self.progress = ProgressTracker(self.config.data_dir)
        self.checkpointer = GitCheckpointer(Path.cwd(), self.config.data_dir / "checkpoints")
        self.harness_loop = HarnessLoop(
            data_dir=self.config.data_dir,
            feature_list=self.feature_list,
            progress=self.progress,
            checkpointer=self.checkpointer,
        )
        self.initializer = HarnessInitializer(
            workspace_root=Path.cwd(),
            data_dir=self.config.data_dir,
            feature_list=self.feature_list,
            progress=self.progress,
        )

        # === Phase 2: Memory ===
        self.memory = UnifiedMemoryManager(self.config, self.session_id, llm=llm)

        # === Phase 3: Sub-Agents ===
        worklog_path = self.config.data_dir.parent / "worklog.md"
        self.subagents = SubAgentOrchestrator(worklog_path=worklog_path)

        # === Phase 4: Plan + Modes ===
        self.plans = PlanManager(self.config.data_dir)
        self.modes = ModeController(self.plans)
        self.compactor = AutoCompactor()

        # === Phase 5: Hooks ===
        self.hooks = HookRegistry()
        self.risk = RiskClassifier()
        self.audit = AuditLog(self.config.data_dir / "audit.jsonl")
        register_governance_hooks(
            registry=self.hooks, classifier=self.risk, audit=self.audit,
            workspace_root=str(Path.cwd()),
        )

        # === Phase 6: Sandbox ===
        self.sandbox_pool = PersistentSandboxPool(self.config.data_dir / "sandboxes")

        # === Phase 7: TUI ===
        self.tui = make_tui()

        # === Phase 8: Proactive ===
        self.event_bus = EventBus(log_path=self.config.data_dir / "events.jsonl")
        self.daemons = DaemonManager(self.event_bus)
        self.daemons.register(FileWatcherDaemon(self.event_bus, Path.cwd(), 15.0))
        self.daemons.register(MemoryDaemon(self.event_bus, self.memory, 300.0))

        # === Phase 9: Protocols ===
        self.mcp_2025 = MCP2025Client()
        self.a2a = A2AClient(my_card=A2AAgentCard(
            name="xeno", description="Xeno 2.0", url="http://localhost:8000"))
        self.agntcy = AGNTCYClient(local_cache=self.config.data_dir / "agntcy_cache.json")
        self.ump_server = UMPAccessController("xeno", self.config.data_dir / "ump_grants.json")

        # Auto-start browser daemon for MCP browser tools
        self._browser_daemon_process: subprocess.Popen | None = None
        try:
            daemon_script = self.config.data_dir / "mcp_servers" / "automation" / "browser_daemon.py"
            if daemon_script.exists():
                self._browser_daemon_process = subprocess.Popen(
                    [sys.executable, str(daemon_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logger.info(f"Browser daemon started (PID {self._browser_daemon_process.pid})")
        except Exception as e:
            logger.warning(f"Failed to start browser daemon: {e}")

        # === Phase 10: Self-Improve ===
        self.skill_miner = SkillMiner(skills_dir=Path("skills"))
        self.ab_tester = ABTestRunner(results_file=self.config.data_dir / "ab_tests.json")
        self.eval_suite = EvalSuite(evals_file=self.config.data_dir / "evals.json")

        # === Phase 11: Production ===
        self.production = ProductionBundle(self.config.data_dir / "production")
        await self.production.startup()

        # === Phase 12: Legacy orchestrator (kept for compat) ===
        self.conversation = ConversationalOrchestrator(
            classifier=InputClassifier(),
            acknowledger=TaskAcknowledger(),
            middle_agent=MiddleAgent(InputClassifier(), TaskAcknowledger()),
        )

        # === Phase 14: Prompt Architecture (Hermes-style) ===
        self.prompt_builder = PromptBuilder()
        self.prompt_builder.load_soul("SOUL.md")
        self.prompt_builder.load_memory("MEMORY.md")
        self.prompt_builder.load_project_context("AGENTS.md")
        self.prompt_tiers = PromptTierBuilder()
        self.context_compressor = ContextCompressor(max_tokens=32000, target_tokens=24000)
        logger.info("Phase 14: Prompt architecture ready (SOUL.md + MEMORY.md + layers)")

        # Tool descriptions for the prompt builder
        try:
            from xeno.tools.registry import TOOL_MAP
            tool_descriptions = [
                {"name": name, "description": getattr(tool, "description", "")[:120]}
                for name, tool in list(TOOL_MAP.items())[:60]
            ]
            self.prompt_builder.set_tools(tool_descriptions)
            self.prompt_tiers.set_tools(tool_descriptions)
        except Exception as e:
            logger.warning(f"Phase 14: tool registration failed: {e}")

        # === Phase 15: Agent-Native Computer Use ===
        self.cdp_bridge = CDPBridge(port=9222)
        self.state_reader = StateReader()
        self.action_planner = ActionPlanner()
        logger.info("Phase 15: Computer use ready (CDP + state reader + action planner)")

        # === Phase 16: Multi-Agent Orchestration ===
        self.supervisor = SupervisorOrchestrator(max_parallel=3)
        self.pipeline = PipelineOrchestrator()
        self.fanout = FanOutOrchestrator(max_parallel=5)
        self.debate = DebateOrchestrator()
        self.adaptive = AdaptiveOrchestrator(max_steps=10)
        logger.info("Phase 16: Orchestration patterns ready (supervisor + pipeline + fanout + debate + adaptive)")

        # === Phase 17: Observability ===
        self.tracer = get_tracer()
        self.tracer.add_exporter(ConsoleExporter(verbose=True))
        self.tracer.add_exporter(FileExporter(self.config.data_dir / "traces.jsonl"))
        self.metrics = get_metrics()
        try:
            self.metrics.load(self.config.data_dir / "metrics.json")
        except Exception:
            pass
        logger.info("Phase 17: Observability ready (tracer + metrics)")

        # === Phase 13: Brain (the NEW main orchestrator) ===
        def _extract_content(result: Any) -> str:
            """Extract text content from various LLM response formats."""
            content = result.content if hasattr(result, "content") else result
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        parts.append(c.get("text", c.get("content", str(c))))
                    else:
                        parts.append(str(c))
                content = " ".join(parts)

            # Detect raw function-call XML from models that don't respect tool_choice="none"
            if isinstance(content, str) and ("<function_calls>" in content or "<invoke " in content):
                return ""

            # If model returned BOTH text content AND tool_calls, just use the text
            tool_calls = getattr(result, "tool_calls", []) or []
            if content and tool_calls:
                return str(content)

            # Handle tool-call-only responses — return empty (natural language was expected)
            if not content and tool_calls:
                return ""

            # Detect empty tool-call responses (Gemini AFC) — return empty
            finish = getattr(result, "response_metadata", {}).get("finish_reason", "")
            if not content and ("UNEXPECTED_TOOL_CALL" in str(finish) or finish == "SAFETY"):
                return ""
            if not content:
                content = str(result)
            return str(content)

        # Text-only LLM variant — disables Gemini AFC for brain/response calls
        _text_llm = llm
        if llm is not None and hasattr(llm, "bind_tools"):
            try:
                _text_llm = llm.bind_tools([], tool_choice="none")
            except Exception:
                pass

        async def _brain_llm(system_prompt: str, user_message: str) -> str:
            """LLM shim for the brain — (system, user) -> response text.
            Uses text-only LLM (no tool calls) to prevent Gemini AFC.
            Flat prompt only — NO prompt builder (avoids tool definitions that trigger function calls).
            """
            if _text_llm is None:
                return ""
            combined = system_prompt + "\n\n" + user_message
            if hasattr(_text_llm, "ainvoke"):
                from langchain_core.messages import HumanMessage
                try:
                    result = await _text_llm.ainvoke([HumanMessage(content=combined)])
                    return _extract_content(result)
                except Exception as e:
                    logger.warning(f"Brain LLM ainvoke failed (retrying as flat prompt): {e}")
                    try:
                        result = await _text_llm.ainvoke(combined)
                        return _extract_content(result)
                    except Exception as e2:
                        logger.warning(f"Brain LLM retry also failed: {e2}")
                        return ""
            elif callable(_text_llm):
                try:
                    result = _text_llm(combined)
                    return _extract_content(result)
                except Exception as e:
                    logger.warning(f"Brain LLM callable failed: {e}")
                    return ""
            return ""

        async def _brain_json_llm(system_prompt: str, user_message: str) -> str:
            """JSON-mode LLM shim for the brain's intent analysis.
            Forces response_format=json_object so the model MUST return valid JSON.
            Falls back to _brain_llm if JSON mode isn't supported.
            """
            if _text_llm is None:
                return ""
            try:
                json_llm = _text_llm.bind(response_format={"type": "json_object"})
                from langchain_core.messages import SystemMessage, HumanMessage
                msgs = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
                result = await json_llm.ainvoke(msgs)
                return _extract_content(result)
            except Exception as e:
                logger.debug(f"JSON LLM failed, falling back to text LLM: {e}")
                return await _brain_llm(system_prompt, user_message)

        self.profile = UserProfile(self.config.data_dir / "profile.json")
        self.brain = Brain(llm=_brain_json_llm)
        self.response_gen = ResponseGenerator(llm=_brain_llm, profile=self.profile)
        self.self_modifier = SelfModifier(project_root=Path.cwd(), llm=_brain_llm)

        # Wire orchestration patterns with agent runner
        async def _agent_runner(agent_name: str, description: str) -> str:
            """Run a task via a named agent (used by orchestration patterns)."""
            if self._main_agent is None:
                from xeno.agent import XenoAgent, load_mcp_tools
                mcp_tools = await load_mcp_tools(self.config)
                self._main_agent = XenoAgent(
                    config=self.config,
                    load_mcp=False,
                    mcp_tools_by_server=mcp_tools,
                )
            return await self._main_agent.run(description)

        if self.supervisor:
            self.supervisor.set_agent_runner(_agent_runner)
            self.supervisor.set_llm(_brain_llm)
        if self.pipeline:
            self.pipeline.set_agent_runner(_agent_runner)
        if self.fanout:
            self.fanout.set_agent_runner(_agent_runner)
        if self.debate:
            self.debate.set_agent_runner(_agent_runner)
            self.debate.set_judge(_brain_llm)
        if self.adaptive:
            self.adaptive.set_agent_runner(_agent_runner)
            self.adaptive.set_llm(_brain_llm)

        # Wire computer use with vision LLM
        if self.state_reader:
            self.state_reader.set_vision_llm(_brain_llm)
        if self.action_planner:
            self.action_planner.set_llm(_brain_llm)

        async def _memory_store_shim(content: str, metadata: dict) -> bool:
            if not self.memory:
                return False
            try:
                await self.memory.remember(
                    content=content, tier="semantic",
                    subject=metadata.get("subject", "user"),
                    importance=0.7,
                    tags=[metadata.get("kind", "user_info")],
                    metadata=metadata,
                )
                return True
            except Exception as e:
                logger.warning(f"Memory store failed: {e}")
                return False

        async def _memory_recall_shim(query: str) -> str:
            if self.memory:
                return self.memory.recall_as_text(query, limit=5)
            return "Memory not available."

        async def _schedule_shim(name: str, prompt: str, sched_type: str, config_json: str) -> str:
            try:
                from xeno.scheduler import get_scheduler
                import json
                sched = get_scheduler()
                if sched:
                    config_dict = json.loads(config_json) if config_json else {}
                    return sched.create(name=name, prompt=prompt,
                                        schedule_type=sched_type, schedule_config=config_dict)
                return "Scheduler not available."
            except Exception as e:
                return f"Schedule failed: {e}"

        async def _web_search_shim(query: str, n: int) -> str:
            try:
                from xeno.tools.advanced_tools import web_search
                return await web_search(query, num_results=n)
            except Exception as e:
                return f"Search failed: {e}"

        self.auto_executor = AutoExecutor(
            profile=self.profile,
            memory_store_fn=_memory_store_shim,
            schedule_create_fn=_schedule_shim,
        )

        # Agent router — picks the right sub-agent for the task via the deepagent.
        # All routing now goes through the single deepagent which uses its sub-agents
        # for specialized work. Standalone agents have been removed — their expertise
        # lives in the sub-agent definitions in agent.py and the main system prompt.

        # Self-improving helpers — capture traces for skill mining
        def _capture_trace(desc: str, source: str, result: str, duration: float = 0.0):
            if self.skill_miner is None:
                return
            from xeno.self_improve import SkillTrace
            import uuid
            self.skill_miner.capture_trace(SkillTrace(
                id=uuid.uuid4().hex[:12],
                task_description=desc,
                steps=[{"tool": source, "result": str(result)[:200]}],
                final_success=True,
                duration_seconds=duration or 0.0,
                tags=[source],
            ))

        def _capture_error(tool: str, args: dict, error: Exception):
            if self.skill_miner is None:
                return
            from xeno.self_improve import ErrorPipeline
            if not hasattr(self, '_error_pipeline'):
                self._error_pipeline = ErrorPipeline(self.skill_miner)
            self._error_pipeline.record_error(tool, args, str(error), {})

        # ── XenoAtlas: Initialize New Subsystems ──────────────────────────────

        # Temporal Knowledge Graph (global)
        try:
            from xeno.memory.temporal import get_temporal_kg
            self.temporal_kg = get_temporal_kg("xeno", storage_path=self.config.data_dir / "temporal_kg")
            logger.info("XenoAtlas: TemporalKG ready")
        except Exception as e:
            logger.warning(f"XenoAtlas: TemporalKG init failed: {e}")

        # Metacognition Pattern Registry
        try:
            from xeno.patterns.registry import register_default_patterns
            register_default_patterns()
            logger.info("XenoAtlas: Pattern registry ready")
        except Exception as e:
            logger.warning(f"XenoAtlas: Pattern registry init failed: {e}")

        # AgentPool (parallel execution engine)
        try:
            from xeno.pool.agent_pool import AgentPool
            self.agent_pool = AgentPool(
                max_workers=self.config.pool_max_workers,
            )
            logger.info(f"XenoAtlas: AgentPool ready ({self.config.pool_max_workers} workers)")
        except Exception as e:
            logger.warning(f"XenoAtlas: AgentPool init failed: {e}")

        # ChatStore (persistent chat history)
        try:
            from xeno.chat.store import ChatStore
            self.chat_store = ChatStore(config=self.config)
            self.chat_store.create_session(model=f"runtime_{self.session_id}")
            logger.info("XenoAtlas: ChatStore ready")
        except Exception as e:
            logger.warning(f"XenoAtlas: ChatStore init failed: {e}")

        # MCP Server Manager (manages MCP server start/stop)
        if self.config.mcp_enabled:
            try:
                from xeno.mcp.lifecycle import MCPServerManager
                self.mcp_lifecycle = MCPServerManager()
                logger.info("XenoAtlas: MCP lifecycle ready")
            except Exception as e:
                logger.warning(f"XenoAtlas: MCP lifecycle init failed: {e}")

        # Security Gateway
        try:
            from xeno.security.gateway import get_gateway
            self.security_gateway = get_gateway()
            logger.info("XenoAtlas: Security gateway ready")
        except Exception as e:
            logger.warning(f"XenoAtlas: Security gateway init failed: {e}")

        # Skill Synthesiser
        try:
            from xeno.skills.synthesiser import get_synthesiser
            self.skill_synthesiser = get_synthesiser()
            logger.info("XenoAtlas: Skill synthesiser ready")
        except Exception as e:
            logger.warning(f"XenoAtlas: Skill synthesiser init failed: {e}")

        # Always-On Agents
        if self.config.always_on_enabled:
            try:
                from xeno.always_on.manager import get_always_on_manager
                self.always_on_manager = get_always_on_manager()

                # Register built-in agents
                from xeno.always_on.whatsapp import create_whatsapp_agent
                whatsapp = create_whatsapp_agent()
                self.always_on_manager.register(whatsapp)

                from xeno.always_on.email import create_email_agent
                email = create_email_agent()
                self.always_on_manager.register(email)

                await self.always_on_manager.start_all()
                logger.info("XenoAtlas: Always-on agents ready")
            except Exception as e:
                logger.warning(f"XenoAtlas: Always-on agents init failed: {e}")

        # Cache for the main deepagent — created once, reused for all task runs
        self._main_agent: Any = None
        self._task_agents: dict[str, Any] = {}

        # Task runner — routes everything through the single deepagent
        async def _brain_task_runner(task_id: str, description: str, intent: Any) -> dict:
            """Run a task through the main deepagent with observability tracing.

            All tasks go through the single deepagent which:
            - Has ALL tools available
            - Uses sub-agents for specialized work (research-agent, coder-agent, etc.)
            - Handles multi-step reasoning and tool chaining natively
            - Inherits conversation memory from the main thread
            """
            # Record in skill synthesiser for pattern detection
            if self.skill_synthesiser:
                try:
                    self.skill_synthesiser.record_tool_call("_brain_task_runner", context=description[:100])
                except Exception:
                    pass

            # Store in chat store
                    if self.chat_store:
                        try:
                            sessions = self.chat_store.list_sessions()
                            if sessions:
                                target_session = sessions[-1]
                                self.chat_store.add_message(target_session.session_id, "user", description[:500])
                        except Exception:
                            pass

            logger.info(f"Task {task_id}: routing to deepagent")
            span_id = ""
            if self.tracer:
                span_id = self.tracer.start_span(f"task.{task_id}", {
                    "description": description[:100],
                    "intent": str(getattr(intent, "intent_type", "unknown")),
                })

            # Build intent context for the agent
            intent_context = ""
            if intent is not None:
                try:
                    intent_context = (
                        f"\n\n## INTENT ANALYSIS\n"
                        f"Type: {getattr(intent, 'intent_type', 'unknown')}\n"
                        f"Goal: {getattr(intent, 'reasoning', description)}\n"
                        f"Estimated complexity: {getattr(intent, 'estimated_seconds', 30)}s\n"
                    )
                except Exception:
                    pass

            # Append contact context (WhatsApp + Gmail) so deepagent knows user's network
            try:
                from xeno.contacts import get_contact_context
                contact_ctx = get_contact_context()
                if contact_ctx:
                    contact_ctx_block = f"\n\n## Contact Network\n{contact_ctx[:1200]}\n"
                    intent_context += contact_ctx_block
            except Exception:
                pass

            # Add search priority instructions for person queries
            intent_context += (
                "\n\n## SEARCH INSTRUCTION\n"
                "When asked about a person, follow this order:\n"
                "1. MEMORY: Check your stored memories about this person.\n"
                "2. CONTACTS: Search WhatsApp contacts with whatsapp_search_contacts().\n"
                "3. CHATS: If found in contacts, read chat history with whatsapp_get_chat_history().\n"
                "4. EMAIL: Search Gmail with gmail_search() for emails from/to this person.\n"
                "5. WEB: ONLY if no results from steps 1-4, use web_search().\n"
                "Always report what you found at each step before moving to the next.\n"
            )

            # Use context compression for intent context
            compressed_description = description
            if self.context_compressor:
                compressed_description = self.context_compressor.compress(description)

            try:
                start_time = time.time()
                result_text = None
                intent_str = getattr(getattr(intent, 'intent_type', None), 'value', '')

                if result_text is None:
                    # Route to the right agent based on intent type
                    from xeno.agent import XenoAgent, load_mcp_tools

                    # Map intent types to dedicated agent instances for true parallelism
                    if intent_str in ("task", "quick_research", "command", "self_modify"):
                        agent_key = intent_str or "main"
                        if agent_key not in self._task_agents:
                            _mcp = await load_mcp_tools(self.config)
                            self._task_agents[agent_key] = XenoAgent(
                                config=self.config,
                                load_mcp=False,
                                mcp_tools_by_server=_mcp,
                            )
                            logger.info(f"Created dedicated {agent_key} agent")
                        agent = self._task_agents[agent_key]
                    else:
                        # Fallback to shared main agent
                        if self._main_agent is None:
                            _mcp = await load_mcp_tools(self.config)
                            self._main_agent = XenoAgent(
                                config=self.config,
                                load_mcp=False,
                                mcp_tools_by_server=_mcp,
                            )
                            logger.info(f"Created cached deepagent for task execution ({len(_mcp)} MCP servers)")
                        agent = self._main_agent

                result_text = await agent.run(
                    compressed_description + intent_context
                )
                duration_s = time.time() - start_time

                # Handle list/dict output formats
                if isinstance(result_text, list):
                    text_parts = []
                    for part in result_text:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    result_text = "".join(text_parts)
                logger.info(f"Task {task_id}: deepagent → {str(result_text)[:200]}")

                # Record metrics
                if self.metrics:
                    self.metrics.record_task("deepagent", duration_s, success=True)
                if self.tracer and span_id:
                    self.tracer.add_attributes(span_id, {"duration_s": duration_s, "success": True})
                    self.tracer.end_span(span_id)

                _capture_trace(description, "deepagent", str(result_text), duration_s)

                # Record result in chat store
                if self.chat_store:
                    try:
                        sessions = self.chat_store.list_sessions()
                        if sessions:
                            self.chat_store.add_message(sessions[-1].session_id, "assistant", str(result_text)[:500])
                    except Exception:
                        pass

                # Record fact in TemporalKG
                if self.temporal_kg:
                    try:
                        self.temporal_kg.add_fact("task_history", f"task_{task_id}",
                            str(description)[:200], source="agent",
                            metadata={"duration": duration_s, "success": True})
                    except Exception:
                        pass

                return {"summary": str(result_text)[:3000], "artifacts": [], "completed_steps": ["Executed via deepagent"]}
            except Exception as e:
                logger.error(f"Task {task_id}: deepagent failed: {e}")
                elapsed = time.time() - start_time
                if self.metrics:
                    self.metrics.record_task("deepagent", elapsed, success=False)
                if self.tracer and span_id:
                    self.tracer.end_span(span_id, status="error", error=str(e))
                # Reset the failed agent (it may be in a bad state)
                if intent_str and intent_str in self._task_agents:
                    self._task_agents.pop(intent_str, None)
                else:
                    self._main_agent = None
                raise  # Let self-healing in orchestrator handle it

        self.context_bridge = AgentContextBridge(self.config.data_dir / "agent_context")

        self.brain_orchestrator = BrainOrchestrator(
            brain=self.brain,
            response_gen=self.response_gen,
            profile=self.profile,
            auto_executor=self.auto_executor,
            task_runner=_brain_task_runner,
            self_modifier=self.self_modifier,
            memory_recall_fn=_memory_recall_shim,
            web_search_fn=_web_search_shim,
            context_bridge=self.context_bridge,
        )

        # Start all subsystems
        self.harness_loop.start_session()
        await self.event_bus.start()
        await self.daemons.start_all()
        await self.conversation.start()
        await self.brain_orchestrator.start()

        # Start background loops
        self._scheduler_task = asyncio.create_task(self._run_scheduler_loop())
        self._watcher_task = asyncio.create_task(self._run_watcher_loop())
        self._improve_task = asyncio.create_task(self._run_self_improve_loop())

        # Clean up stale WhatsApp schedules from previous sessions
        try:
            from xeno.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                stale_ids = [tid for tid, t in list(sched.tasks.items()) if "whatsapp" in t.name.lower()]
                for tid in stale_ids:
                    sched.delete(tid)
                if stale_ids:
                    logger.info(f"Cleaned {len(stale_ids)} stale WhatsApp schedule(s) from disk")
        except Exception:
            pass

        self.startup_context = await self.initializer.initialize()
        self.started = True
        logger.info("Xeno 2.0 runtime ready — all 13 phases online (Brain-driven)")
        return self.startup_context

    async def _run_self_improve_loop(self) -> None:
        """Background loop: periodically mine skills and error patterns.

        Runs every 300s (5 min). Consolidates successful traces into
        reusable skills in skills/ directory.
        """
        while True:
            try:
                await asyncio.sleep(300)
                if self.skill_miner is None:
                    continue

                # Mine reusable skills from successful traces
                new_skills = await self.skill_miner.mine_skills(max_skills=3)
                if new_skills:
                    skills_dir = Path("skills")
                    skills_dir.mkdir(parents=True, exist_ok=True)
                    for skill in new_skills:
                        skill_path = skills_dir / f"{skill.name[:40].replace(':', '_')}.md"
                        content = (
                            f"# {skill.name}\n\n"
                            f"**Auto-mined skill** (confidence: {skill.confidence:.1f})\n\n"
                            f"## Description\n{skill.description}\n\n"
                            f"## Trigger\n{skill.trigger_pattern}\n\n"
                            f"## Procedure\n"
                        )
                        for step in skill.procedure:
                            content += f"- {step.get('action', str(step))}\n"
                        content += f"\n*Source: {skill.source.value}*\n"
                        skill_path.write_text(content, encoding="utf-8")
                        logger.info(f"Self-improve: created skill '{skill.name}' → {skill_path}")

                # Generate error prevention skills
                if hasattr(self, '_error_pipeline'):
                    err_skills = await self._error_pipeline.generate_prevention_skills(threshold=5)
                    if err_skills:
                        for skill in err_skills:
                            logger.info(f"Self-improve: created prevention skill '{skill.name}'")

                logger.debug(f"Self-improve cycle complete ({len(new_skills)} new skills)")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Self-improve cycle error: {e}")

    async def _run_scheduler_loop(self) -> None:
        """Background loop: poll for due scheduled tasks.

        When a scheduled task fires:
        - If it's a REMINDER (like "go for a walk") → just display it
        - If it's an ACTION (like "open youtube") → actually execute it, then display the result
        """
        results_file = self.config.data_dir / "reminder_results.json"
        last_results: list[dict] = []
        if results_file.exists():
            try:
                last_results = json.loads(results_file.read_text())
            except Exception:
                last_results = []

        # Action keywords — if the prompt contains these, EXECUTE the task
        ACTION_KEYWORDS = [
            "open ", "launch ", "start ", "go to ", "navigate to ",
            "search ", "search for ", "look up ", "find ",
            "run ", "execute ", "pip install", "npm install", "git ",
            "write ", "create ", "make ", "build ",
            "send ", "message ",
            "screenshot", "take a screenshot",
        ]

        while True:
            try:
                await asyncio.sleep(2)
                from xeno.scheduler import get_scheduler
                sched = get_scheduler()
                if not sched:
                    continue
                due_tasks = sched.get_due_tasks()
                if not due_tasks:
                    continue
                logger.info("Scheduler: %d due task(s) found", len(due_tasks))

                for task in due_tasks:
                    try:
                        sched.mark_executed(task.id)
                        prompt_lower = task.prompt.lower()

                        # Check if this is an ACTION or just a REMINDER
                        is_action = any(kw in prompt_lower for kw in ACTION_KEYWORDS)

                        if is_action and self.brain_orchestrator:
                            # It's an ACTION — execute it via the brain orchestrator
                            logger.info(f"Scheduler: executing action '{task.name}': {task.prompt}")
                            await self.brain_orchestrator.handle_user_input(task.prompt)
                        elif self.brain_orchestrator:
                            # It's a REMINDER — just display it
                            await self.brain_orchestrator.emit_reminder(task.name, task.prompt)
                        elif self.notify_callback:
                            self.notify_callback(f"⏰ {task.name}: {task.prompt}")

                        from datetime import datetime, timezone
                        last_results.append({
                            "task": task.name,
                            "prompt": task.prompt,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "type": "action" if is_action else "reminder",
                        })
                        if len(last_results) > 20:
                            last_results = last_results[-20:]
                        results_file.write_text(json.dumps(last_results, indent=2))
                        logger.info("Scheduler: fired %s '%s'", "action" if is_action else "reminder", task.name)
                    except Exception as e:
                        logger.error("Scheduler: task '%s' failed: %s", task.name, e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

    async def _run_watcher_loop(self) -> None:
        """Watch agents/, skills/, plugins/ for changes and hot-reload."""
        if not self.config.hot_reload:
            await asyncio.sleep(999999)
            return
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class ReloadHandler(FileSystemEventHandler):
                def __init__(self, runtime):
                    self.runtime = runtime

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    path = Path(event.src_path)
                    if path.suffix == ".md" and "skills" in str(path):
                        logger.info(f"Hot-reload: skill changed → {path.name}")
                    elif path.suffix == ".py" and ("agents" in str(path) or "plugins" in str(path)):
                        logger.info(f"Hot-reload: agent/plugin changed → {path.name}")

            observer = Observer()
            for watch_dir in [Path("agents"), Path("skills"), Path("plugins")]:
                if watch_dir.exists():
                    observer.schedule(ReloadHandler(self), str(watch_dir), recursive=True)
            observer.start()
            while True:
                await asyncio.sleep(1)
        except ImportError:
            logger.info("watchdog not installed — hot-reload disabled")
            await asyncio.sleep(999999)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Watcher loop error: {e}")

    async def shutdown(self) -> None:
        if not self.started:
            return
        logger.info("Shutting down Xeno 2.0 runtime...")
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try: await self._scheduler_task
            except asyncio.CancelledError: pass
        if self._improve_task:
            self._improve_task.cancel()
            try: await self._improve_task
            except asyncio.CancelledError: pass
        if self._watcher_task:
            self._watcher_task.cancel()
            try: await self._watcher_task
            except asyncio.CancelledError: pass
        if self.daemons: await self.daemons.stop_all()
        if self.event_bus: await self.event_bus.stop()
        if self.conversation: await self.conversation.stop()
        if self.brain_orchestrator: await self.brain_orchestrator.stop()
        if self.memory:
            try: await self.memory.sleep.run_light_cycle()
            except: pass
        if self.metrics:
            try: self.metrics.save(self.config.data_dir / "metrics.json")
            except: pass
        if self.tracer:
            self.tracer.clear()
        if self.cdp_bridge:
            try: await self.cdp_bridge.close()
            except: pass
        if self.harness_loop: self.harness_loop.end_session()
        if self.production: await self.production.shutdown()
        if self.sandbox_pool: self.sandbox_pool.close_all()
        if hasattr(self, '_browser_daemon_process') and self._browser_daemon_process:
            try:
                self._browser_daemon_process.terminate()
                self._browser_daemon_process.wait(timeout=5)
                logger.info("Browser daemon stopped")
            except Exception as e:
                logger.warning(f"Browser daemon shutdown: {e}")

        # ── XenoAtlas Shutdown ──────────────────────────────────────────────
        if self.always_on_manager:
            try:
                await self.always_on_manager.stop_all()
                logger.info("XenoAtlas: Always-on agents stopped")
            except Exception as e:
                logger.warning(f"Always-on manager shutdown: {e}")
        if self.agent_pool:
            try:
                if hasattr(self.agent_pool, 'shutdown'):
                    await self.agent_pool.shutdown()
                logger.info("XenoAtlas: AgentPool stopped")
            except Exception as e:
                logger.warning(f"AgentPool shutdown: {e}")
        if self.chat_store:
            try:
                if hasattr(self.chat_store, 'save'):
                    self.chat_store.save()
                logger.info("XenoAtlas: ChatStore saved")
            except Exception as e:
                logger.warning(f"ChatStore shutdown: {e}")
        if self.temporal_kg:
            try:
                if hasattr(self.temporal_kg, 'save'):
                    self.temporal_kg.save()
                logger.info("XenoAtlas: TemporalKG saved")
            except Exception as e:
                logger.warning(f"TemporalKG shutdown: {e}")
        if self.mcp_lifecycle:
            try:
                await self.mcp_lifecycle.stop()
                logger.info("XenoAtlas: MCP lifecycle stopped")
            except Exception as e:
                logger.warning(f"MCP lifecycle shutdown: {e}")
        # ── End XenoAtlas Shutdown ──────────────────────────────────────────

        self.started = False
        logger.info("Xeno 2.0 runtime shutdown complete")

    def status(self) -> dict:
        if not self.started:
            return {"status": "not_started"}
        return {
            "session_id": self.session_id,
            "started": self.started,
            "memory": self.memory.full_summary() if self.memory else None,
            "profile": self.profile.stats() if self.profile else None,
            "brain_orchestrator": self.brain_orchestrator.status() if self.brain_orchestrator else None,
            "production": self.production.status() if self.production else None,
            "daemons": self.daemons.list_daemons() if self.daemons else None,
            "prompt": {
                "builder_cached_layers": len(self.prompt_builder._layer_cache) if self.prompt_builder else 0,
                "tier_cache_stats": self.prompt_tiers.cache_stats if self.prompt_tiers else None,
            } if self.prompt_builder else None,
            "computer_use": {
                "cdp_connected": self.cdp_bridge._connected if self.cdp_bridge else False,
            } if self.cdp_bridge else None,
            "orchestration": {
                "supervisor": self.supervisor.get_status() if self.supervisor else None,
            } if self.supervisor else None,
            "observability": {
                "metrics": len(self.metrics._series) if self.metrics else 0,
            } if self.metrics else None,
            "xenoatlas": {
                "agent_pool": self.agent_pool.list_active() if self.agent_pool else "N/A",
                "chat_store": len(self.chat_store.list_sessions()) if self.chat_store else "N/A",
                "always_on": self.always_on_manager.get_status() if self.always_on_manager else "N/A",
                "temporal_kg": self.temporal_kg.export_context(limit=3) if self.temporal_kg else "N/A",
                "skill_synthesiser": self.skill_synthesiser.get_status() if self.skill_synthesiser else "N/A",
                "security": self.security_gateway.get_stats() if self.security_gateway else "N/A",
            },
        }
