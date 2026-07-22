"""Xeno 2.0 — entry point.

Usage:
    python xeno2.py              # Interactive TUI
    python xeno2.py --check      # Health check
    python xeno2.py --status     # System status
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for name in ("httpx", "httpcore", "chromadb", "urllib3", "asyncio",
             "google_genai", "langchain_google_genai", "langchain",
             "langgraph", "langchain_core", "langchain_groq", "groq",
             "openai", "httpcore", "character_ai", "chromadb",
             "xeno.always_on", "xeno.dynamic.discovery", "xeno.dynamic",
             "xeno.tool_registry", "xeno.client",
             "xeno.agent", "xeno.runtime", "xeno.production",
             "xeno.middle", "xeno.middle.orchestrator",
             "xeno.brain", "xeno.brain.orchestrator",
             "xeno.profile", "xeno.auto", "xeno.memory",
             "xeno.harness", "xeno.hooks", "xeno.sandbox",
             "xeno.subagents", "xeno.plan", "xeno.protocols",
             "xeno.self_improve", "xeno.self_mod"):
    logging.getLogger(name).setLevel(logging.WARNING)

logger = logging.getLogger("xeno2")


async def interactive_mode():
    from xeno.config import XenoConfig
    from xeno.runtime import XenoRuntime
    from xeno.tui import make_tui

    config = XenoConfig.from_env()
    runtime = XenoRuntime(config=config)

    # Auto-initialize LLM if possible
    llm = None
    try:
        from xeno.client import get_llm_client
        llm = get_llm_client(config)
        if llm:
            logger.info(f"LLM ready: {config.provider}/{config.model}")
    except Exception as e:
        logger.warning(f"Could not initialize LLM: {e}")

    print("Starting Xeno 2.0...")
    startup_ctx = await runtime.startup(llm=llm)
    print(f"Session: {runtime.session_id}\n")

    tui = make_tui()
    if tui is not None:
        runtime.notify_callback = lambda msg: tui.assistant_response(msg)
    if tui is None:
        await _plain_cli(runtime, startup_ctx)
    else:
        await _rich_cli(runtime, startup_ctx, tui)

    await runtime.shutdown()


async def _conversation_loop(runtime, tui):
    """Main conversation loop driven by the BrainOrchestrator (LLM-driven).

    FIX: handle_user_input now WAITS for tasks to complete, so AFTER_WORK
    shows immediately (not on next input).
    """
    from xeno.brain.orchestrator import BrainEventType

    events_q = runtime.brain_orchestrator.subscribe()

    async def display_events():
        """Background task that displays events as they arrive."""
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=0.3)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            _icons = {
                BrainEventType.BEFORE_WORK: "[WORK]",
                BrainEventType.INSTANT_REPLY: "",
                BrainEventType.PROGRESS: "[...]",
                BrainEventType.QUEUED: "[Q]",
                BrainEventType.QUEUE_STARTED: "[START]",
                BrainEventType.SELF_MOD_RESULT: "[MOD]",
                BrainEventType.REMINDER: "[!]",
                BrainEventType.INFO: "[i]",
            }
            _icon = _icons.get(ev.type, "")
            msg = f"{_icon} {ev.message}" if _icon else ev.message

            if ev.type == BrainEventType.BEFORE_WORK:
                tui.info(msg)
            elif ev.type == BrainEventType.INSTANT_REPLY:
                tui.assistant_response(msg)
            elif ev.type == BrainEventType.PROGRESS:
                tui.info(msg)
            elif ev.type == BrainEventType.AFTER_WORK:
                tui.divider()
                tui.success(msg)
            elif ev.type == BrainEventType.AFTER_FAILURE:
                tui.divider()
                tui.error(msg)
            elif ev.type == BrainEventType.QUEUED:
                tui.info(msg)
            elif ev.type == BrainEventType.QUEUE_STARTED:
                tui.info(msg)
            elif ev.type == BrainEventType.SELF_MOD_RESULT:
                tui.info(msg)
            elif ev.type == BrainEventType.REMINDER:
                tui.divider()
                tui.warning(msg)
                tui.divider()
            elif ev.type == BrainEventType.INFO:
                tui.info(msg)
            else:
                tui.info(msg)

    display_task = asyncio.create_task(display_events())

    try:
        while True:
            try:
                user_input = await tui.user_prompt()
            except (EOFError, KeyboardInterrupt):
                break
            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/quit", "/exit", "/q"):
                    break
                elif cmd == "/status":
                    tui.status_panel(runtime.status())
                    continue
                elif cmd == "/help":
                    tui.slash_command_help()
                    continue
                elif cmd == "/memory":
                    if runtime.memory:
                        tui.console.print(runtime.memory.full_summary())
                    continue
                elif cmd == "/profile":
                    if runtime.profile:
                        tui.console.print(json.dumps(runtime.profile.full_profile(), indent=2, default=str))
                    continue
                elif cmd == "/sleep":
                    tui.info("Running memory sleep cycle...")
                    if runtime.memory:
                        result = await runtime.memory.reflect_now()
                        tui.success(f"Sleep cycle complete: {result}")
                    continue
                elif cmd == "/tasks":
                    status = runtime.brain_orchestrator.status()
                    tui.console.print(f"  Running: {status.get('running_task')}")
                    tui.console.print(f"  Queue size: {status.get('queue_size', 0)}")
                    continue
                elif cmd.startswith("/cancel"):
                    if runtime.brain_orchestrator and runtime.brain_orchestrator._running_task:
                        runtime.brain_orchestrator._running_task.task.cancel()
                        tui.warning("Cancelling current task...")
                    else:
                        tui.info("No running task to cancel.")
                    continue
                else:
                    tui.warning(f"Unknown command: {user_input}")
                    continue

            # Process user input — handle_user_input now WAITS for task completion
            tui.thinking()
            try:
                await runtime.brain_orchestrator.handle_user_input(user_input)
            finally:
                tui.clear_thinking()
            # Small delay to let any final events flush
            await asyncio.sleep(0.05)
    finally:
        display_task.cancel()
        try:
            await display_task
        except asyncio.CancelledError:
            pass


async def _rich_cli(runtime, startup_ctx, tui):
    tui.set_mode("CHAT", "Xeno 2.0 ready")
    tui.header()
    if startup_ctx.user_intent:
        tui.info(f"Intent: {startup_ctx.user_intent}")
    if startup_ctx.active_features:
        tui.info(f"Active features: {len(startup_ctx.active_features)}")
    tui.info("Tip: tell me about yourself, ask questions, or give me tasks.")
    print()
    await _conversation_loop(runtime, tui)
    tui.divider()
    tui.info("Shutting down...")


async def _plain_cli(runtime, startup_ctx):
    print(f"\nXeno 2.0 — session {runtime.session_id}")
    print("Commands: /status /memory /profile /tasks /cancel /quit\n")
    from xeno.brain.orchestrator import BrainEventType
    events_q = runtime.brain_orchestrator.subscribe()

    async def display_events():
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            prefix = {
                BrainEventType.BEFORE_WORK: "🚀", BrainEventType.INSTANT_REPLY: "💬",
                BrainEventType.PROGRESS: "⏳", BrainEventType.AFTER_WORK: "✅",
                BrainEventType.AFTER_FAILURE: "❌", BrainEventType.QUEUED: "📋",
                BrainEventType.QUEUE_STARTED: "▶️", BrainEventType.SELF_MOD_RESULT: "🔧",
                BrainEventType.REMINDER: "⏰",
                BrainEventType.INFO: "ℹ️",
            }.get(ev.type, "•")
            print(f"\n{prefix} {ev.message}")
            # Redraw the prompt so it's not lost
            print("you> ", end="", flush=True)

    display_task = asyncio.create_task(display_events())
    try:
        while True:
            try:
                user_input = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                continue
            if user_input in ("/quit", "/exit"):
                break
            if user_input == "/status":
                print(json.dumps(runtime.status(), indent=2, default=str))
                continue
            await runtime.brain_orchestrator.handle_user_input(user_input)
    finally:
        display_task.cancel()
        try:
            await display_task
        except asyncio.CancelledError:
            pass
    print("\nShutting down...")


def health_check():
    print("Xeno 2.0 Health Check")
    print("=" * 50)
    checks = [
        ("Phase 1: Harness", "xeno.harness"),
        ("Phase 2: Unified Memory", "xeno.memory.unified"),
        ("Phase 3: Sub-Agents", "xeno.subagents.isolated"),
        ("Phase 4: Plan", "xeno.plan"),
        ("Phase 5: Hooks", "xeno.hooks"),
        ("Phase 6: Sandbox", "xeno.sandbox"),
        ("Phase 7: TUI", "xeno.tui"),
        ("Phase 8: Proactive", "xeno.proactive"),
        ("Phase 9: Protocols", "xeno.protocols"),
        ("Phase 10: Self-Improve", "xeno.self_improve"),
        ("Phase 11: Production", "xeno.production"),
        ("Phase 12: Middle (legacy)", "xeno.middle"),
        ("Phase 13: Brain", "xeno.brain"),
        ("Phase 13: Profile", "xeno.profile"),
        ("Phase 13: Auto Executor", "xeno.auto"),
        ("Phase 13: Self-Mod", "xeno.self_mod"),
        ("Integration: Runtime", "xeno.runtime"),
    ]
    passed = 0
    for name, module in checks:
        try:
            __import__(module)
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    print("=" * 50)
    print(f"{passed}/{len(checks)} subsystems OK")


def main():
    parser = argparse.ArgumentParser(description="Xeno 2.0")
    parser.add_argument("--check", action="store_true", help="Health check")
    parser.add_argument("--status", action="store_true", help="System status")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.check:
        health_check()
    elif args.status:
        from xeno.config import XenoConfig
        c = XenoConfig.from_env()
        print(f"Data dir: {c.data_dir}")
        print(f"Model: {c.model}")
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
