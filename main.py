"""Xeno CLI — uses the Brain Orchestrator for proper before/after work + background tasks.

Features:
- Brain analyzes every message (LLM intent classification)
- BEFORE_WORK: Real answer before starting a task
- Tasks run in BACKGROUND (fire-and-forget) — user can keep chatting
- AFTER_WORK: Shows whenever task completes (not on next input)
- Stop/cancel: say "stop" to instantly cancel running tasks
- Self-healing: failed tools/agents are auto-fixed and retried
- Sub-agents: delegate complex work via the task() tool
- Reminders: scheduled tasks fire while you're chatting
- Quick replies: chat, research, memory queries answered instantly
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Windows asyncio setup — only needed for Python < 3.14 (3.14+ uses Proactor by default)
if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("xeno")

# Suppress noisy loggers
for name in ("httpx", "httpcore", "chromadb", "urllib3", "asyncio", "watchdog"):
    logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================================
# Colors for terminal output (Windows-compatible)
# ============================================================================

# Detect Windows codepage for safe Unicode
def _is_unicode_safe():
    try:
        "✓".encode(sys.stdout.encoding or "utf-8")
        return True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False

_UNICODE_OK = _is_unicode_safe()

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def _ok() -> str: return "✓" if _UNICODE_OK else "[OK]"
def _fail() -> str: return "✗" if _UNICODE_OK else "[FAIL]"

def colored(text: str, color: str) -> str:
    return f"{color}{text}{C.RESET}"


# ============================================================================
# Interactive CLI — uses the Brain Orchestrator
# ============================================================================

async def cli_loop(model_override: str = None):
    """Main interactive CLI loop using the Brain Orchestrator.

    This is the SAME flow as xeno2.py — it uses runtime.brain_orchestrator
    which handles:
    - BEFORE_WORK / AFTER_WORK
    - Background tasks (fire-and-forget)
    - Stop/cancel
    - Self-healing
    - Sub-agents
    - Reminders
    """
    from xeno.config import XenoConfig
    from xeno.runtime import XenoRuntime

    # Build config
    config = XenoConfig.from_env()
    if model_override:
        config.model = model_override
        os.environ["XENO_MODEL"] = model_override

    # Header
    print()
    print(colored("=" * 60, C.CYAN))
    print(colored("  Xeno — Advanced AI Agent (deepagents-powered)", C.BOLD))
    print(colored(f"  Model: {config.model}", C.DIM))
    print(colored("=" * 60, C.CYAN))
    print()
    print(colored("  Commands:", C.WHITE))
    print(colored("    <anything>       chat with the agent", C.WHITE))
    print(colored("    stop             stop the current task", C.RED))
    print(colored("    tasks            list background tasks", C.YELLOW))
    print(colored("    tools            list available tools", C.BLUE))
    print(colored("    agents           list sub-agents", C.MAGENTA))
    print(colored("    sched            list scheduled tasks", C.CYAN))
    print(colored("    memory           show memory summary", C.CYAN))
    print(colored("    reset            reset conversation", C.YELLOW))
    print(colored("    quit / exit      shutdown", C.DIM))
    print()

    # Create the runtime (includes brain orchestrator)
    print(colored("Initializing agent...", C.DIM), end=" ", flush=True)
    try:
        # Auto-initialize LLM
        llm = None
        try:
            from xeno.client import get_llm_client
            llm = get_llm_client(config)
            if llm:
                logger.info(f"LLM ready: {config.provider}/{config.model}")
        except Exception as e:
            logger.warning(f"Could not initialize LLM: {e}")

        runtime = XenoRuntime(config=config)
        startup_ctx = await runtime.startup(llm=llm)
        print(colored("ready.", C.GREEN))
    except Exception as e:
        print(colored(f"failed: {e}", C.RED))
        logger.error(f"Agent initialization failed: {e}", exc_info=True)
        return
    print()

    # Subscribe to brain events
    from xeno.brain.orchestrator import BrainEventType
    events_q = runtime.brain_orchestrator.subscribe()

    # Background task that displays events as they arrive
    # Use \r to clear the "you> " prompt before printing messages
    async def display_events():
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=0.3)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            _eicons = {
                BrainEventType.BEFORE_WORK: "[WORK]",
                BrainEventType.INSTANT_REPLY: "",
                BrainEventType.PROGRESS: "[...]",
                BrainEventType.QUEUED: "[Q]",
                BrainEventType.QUEUE_STARTED: "[START]",
                BrainEventType.SELF_MOD_RESULT: "[MOD]",
                BrainEventType.REMINDER: "[!]",
                BrainEventType.INFO: "[i]",
            }
            _msg = f"{_eicons.get(ev.type, '')} {ev.message}" if _eicons.get(ev.type, '') else ev.message
            # Clear the "you> " prompt line before printing event messages
            prefix = "\r" + " " * 80 + "\r"
            if ev.type == BrainEventType.BEFORE_WORK:
                print(f"{prefix}{colored(_msg, C.BLUE)}")
            elif ev.type == BrainEventType.INSTANT_REPLY:
                print(f"{prefix}{colored(_msg, C.GREEN)}")
            elif ev.type == BrainEventType.PROGRESS:
                print(f"{prefix}{colored(_msg, C.YELLOW)}")
            elif ev.type == BrainEventType.AFTER_WORK:
                label = ev.task_label or "Task"
                print(f"{prefix}"
                    f"{colored('='*50, C.GREEN)}\n"
                    f"{colored(f'  ✓ {label}', C.GREEN)}\n"
                    f"{colored(f'  {_msg}', C.GREEN)}\n"
                    f"{colored('='*50, C.GREEN)}")
            elif ev.type == BrainEventType.AFTER_FAILURE:
                print(f"{prefix}"
                    f"{colored('='*50, C.RED)}\n"
                    f"{colored(f'  ✗ Failed: {_msg}', C.RED)}\n"
                    f"{colored('='*50, C.RED)}")
            elif ev.type == BrainEventType.QUEUED:
                print(f"{prefix}{colored(_msg, C.BLUE)}")
            elif ev.type == BrainEventType.QUEUE_STARTED:
                print(f"{prefix}{colored(_msg, C.BLUE)}")
            elif ev.type == BrainEventType.SELF_MOD_RESULT:
                print(f"{prefix}{colored(_msg, C.MAGENTA)}")
            elif ev.type == BrainEventType.REMINDER:
                print(f"{prefix}")
                print(colored(f"  {_msg}", C.YELLOW))
            elif ev.type == BrainEventType.INFO:
                print(f"{prefix}{colored(_msg, C.DIM)}")
            else:
                print(f"{prefix}  {_msg}")

    display_task = asyncio.create_task(display_events())

    # Main loop — async user prompt so event loop isn't blocked
    loop = asyncio.get_event_loop()
    try:
        while True:
            try:
                user_input = await loop.run_in_executor(None, lambda: input(colored("you> ", C.CYAN)))
            except (EOFError, KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                logger.warning(f"Input error: {e}")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Commands
            cmd = user_input.lower()
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "reset":
                runtime.brain_orchestrator._running_task = None
                runtime.brain_orchestrator._queue.clear()
                print(colored("  Conversation reset.", C.YELLOW))
                continue
            elif cmd == "tools":
                from xeno.tools.registry import get_all_tool_names
                tools = get_all_tool_names()
                print(colored(f"  Available tools ({len(tools)}):", C.BLUE))
                for t in tools:
                    print(f"    {t}")
                continue
            elif cmd == "agents":
                from xeno.subagents import get_all_subagents
                subs = get_all_subagents(config)
                print(colored(f"  Sub-agents ({len(subs)}):", C.MAGENTA))
                for sa in subs:
                    print(f"    {colored(sa['name'], C.MAGENTA)} — {sa['description'][:60]}")
                continue
            elif cmd == "schedules" or cmd == "sched":
                try:
                    from xeno.scheduler import get_scheduler
                    sched = get_scheduler()
                    if sched:
                        print(colored("  Schedules:", C.CYAN))
                        print(f"    {sched.list_all()}")
                    else:
                        print(colored("  Scheduler not available", C.RED))
                except Exception as e:
                    print(colored(f"  Error: {e}", C.RED))
                continue
            elif cmd == "memory":
                if runtime.memory:
                    print(colored("  Memory summary:", C.CYAN))
                    print(runtime.memory.get_full_context())
                continue
            elif cmd == "profile":
                if runtime.profile:
                    import json
                    print(json.dumps(runtime.profile.full_profile(), indent=2, default=str))
                continue
            elif cmd == "tasks":
                status = runtime.brain_orchestrator.status()
                print(f"  Running: {status.get('running_task')}")
                print(f"  Queue size: {status.get('queue_size', 0)}")
                continue
            elif cmd == "status":
                print(runtime.status())
                continue
            elif cmd == "help":
                print(colored("  Commands:", C.BOLD))
                print(f"    {colored('<text>', C.WHITE)}       chat or task")
                print(f"    {colored('stop', C.RED)}          stop current task")
                print(f"    {colored('tasks', C.YELLOW)}       list tasks")
                print(f"    {colored('tools', C.BLUE)}        list tools")
                print(f"    {colored('agents', C.MAGENTA)}      list sub-agents")
                print(f"    {colored('memory', C.CYAN)}       memory summary")
                print(f"    {colored('sched', C.CYAN)}        list schedules")
                print(f"    {colored('reset', C.YELLOW)}       reset conversation")
                print(f"    {colored('quit', C.DIM)}         exit")
                continue

            # All user input goes through the brain orchestrator
            # It handles: stop/cancel, quick replies, tasks (background), reminders, etc.
            try:
                await runtime.brain_orchestrator.handle_user_input(user_input)
            except Exception as e:
                print(colored(f"  Error: {e}", C.RED))
                logger.error(f"handle_user_input failed: {e}", exc_info=True)

            # Small delay to let events flush
            await asyncio.sleep(0.05)
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        display_task.cancel()
        try:
            await asyncio.wait_for(display_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass
        # Cancel all running background tasks first so shutdown is clean
        try:
            runtime.brain_orchestrator._running_tasks.clear()
        except Exception:
            pass
        try:
            await asyncio.wait_for(runtime.shutdown(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            pass

    print(colored("\nGoodbye!", C.CYAN))


# ============================================================================
# Server mode
# ============================================================================

def serve_mode(host: str, port: int, model_override: str = None):
    """Start the FastAPI server."""
    if model_override:
        os.environ["XENO_MODEL"] = model_override
    from xeno.server import app
    import uvicorn
    print(f"Starting Xeno server on {host}:{port}")
    print(f"Docs: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="info")


# ============================================================================
# Scan mode
# ============================================================================

def scan_mode():
    """List discovered agents, plugins, and skills."""
    from xeno.config import XenoConfig
    config = XenoConfig.from_env()

    print(colored("=" * 60, C.CYAN))
    print(colored("  Xeno Component Scanner", C.BOLD))
    print(colored("=" * 60, C.CYAN))

    print(colored("\n  [SUB-AGENTS]", C.BOLD))
    try:
        from xeno.subagents import get_all_subagents
        subs = get_all_subagents(config)
        for sa in subs:
            print(f"    {colored(sa['name'], C.MAGENTA)} — {sa['description'][:60]}")
    except Exception as e:
        print(f"    Error: {e}")

    print(colored("\n  [TOOLS]", C.BOLD))
    try:
        from xeno.tools.registry import get_all_tool_names
        tools = get_all_tool_names()
        print(f"    {len(tools)} tools available:")
        for t in tools:
            print(f"      {t}")
    except Exception as e:
        print(f"    Error: {e}")

    print(colored("\n  [SKILLS]", C.BOLD))
    try:
        from xeno.skills_manager import get_skills_manager
        sm = get_skills_manager()
        if sm:
            skills = sm.list_skills()
            print(f"    {len(skills)} skills:")
            for s in skills[:20]:
                print(f"      {s.get('name', '?')}: {s.get('description', '')[:60]}")
    except Exception as e:
        print(f"    Error: {e}")


# ============================================================================
# Health check
# ============================================================================

def check_mode():
    """Verify all subsystems load correctly."""
    print(colored("Xeno Health Check", C.BOLD))
    print("=" * 50)

    checks = [
        ("deepagents (real library)", "deepagents"),
        ("LangChain core", "langchain_core"),
        ("LangGraph", "langgraph"),
        ("Xeno config", "xeno.config"),
        ("Xeno agent", "xeno.agent"),
        ("Xeno tools registry", "xeno.tools.registry"),
        ("Xeno sub-agents", "xeno.subagents"),
        ("Xeno brain orchestrator", "xeno.brain.orchestrator"),
        ("Xeno runtime", "xeno.runtime"),
        ("Xeno memory", "xeno.memory"),
        ("Xeno scheduler", "xeno.scheduler"),
        ("Xeno skills manager", "xeno.skills_manager"),
        ("Xeno todos", "xeno.todos"),
        ("Xeno self-heal", "xeno.self_heal"),
        ("Xeno MCP client", "xeno.mcp_client"),
        ("Xeno prompt architecture", "xeno.prompt.builder"),
        ("Xeno computer use", "xeno.computer_use.cdp_bridge"),
        ("Xeno orchestration", "xeno.orchestration.supervisor"),
        ("Xeno observability", "xeno.observability.tracer"),
        ("Xeno SOUL.md", "SOUL.md"),
        ("Xeno MEMORY.md", "MEMORY.md"),
    ]

    passed = 0
    for name, module in checks:
        try:
            __import__(module)
            print(f"  {colored(_ok(), C.GREEN)} {name}")
            passed += 1
        except Exception as e:
            print(f"  {colored(_fail(), C.RED)} {name}: {e}")

    print("=" * 50)
    print(f"{colored(str(passed), C.GREEN)}/{len(checks)} subsystems OK")

    # Verify real deepagents
    print()
    try:
        import deepagents
        import inspect
        loc = inspect.getfile(deepagents.create_deep_agent)
        if "site-packages" in loc:
            print(f"  {colored(_ok(), C.GREEN)} Real deepagents library")
        else:
            print(f"  {colored(_fail(), C.RED)} Fake deepagents shim detected")
    except Exception as e:
        print(f"  {colored(_fail(), C.RED)} Cannot verify deepagents: {e}")

    # Verify brain orchestrator features
    try:
        from xeno.brain.orchestrator import BrainOrchestrator
        assert hasattr(BrainOrchestrator, '_cancel_running_task')
        assert hasattr(BrainOrchestrator, '_self_heal')
        assert hasattr(BrainOrchestrator, '_start_task_background')
        print(f"  {colored(_ok(), C.GREEN)} Brain orchestrator: stop/cancel + self-heal + background tasks")
    except Exception as e:
        print(f"  {colored(_fail(), C.RED)} Brain orchestrator issue: {e}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Xeno — Advanced AI Agent (deepagents-powered)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--serve", action="store_true", help="Start REST API server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--scan", action="store_true", help="List agents/plugins/skills")
    parser.add_argument("--check", action="store_true", help="Health check")
    parser.add_argument("--model", default=None, help="Override model")
    parser.add_argument("prompt", nargs="*", help="Prompt to send directly")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("xeno").setLevel(logging.DEBUG)

    if args.check:
        check_mode()
    elif args.scan:
        scan_mode()
    elif args.serve:
        serve_mode(args.host, args.port, args.model)
    else:
        asyncio.run(cli_loop(args.model))


if __name__ == "__main__":
    main()
