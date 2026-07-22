"""Xeno Server — production FastAPI server.

Starts the full Xeno system on startup: dynamic discovery, memory,
agents, MCP, plugins, hot-reload. Serves 50+ REST endpoints.

Usage:
    python -m xeno.server                    # default :8000
    python -m xeno.server --port 9000        # custom port
    python -m xeno.server --host 127.0.0.1   # custom host
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("xeno.server")

# ---------------------------------------------------------------------------
# Global state — initialized on startup
# ---------------------------------------------------------------------------
_wrapper = None
_dashboard = None


def get_wrapper():
    global _wrapper
    if _wrapper is None:
        raise RuntimeError("Server not initialized. Call startup first.")
    return _wrapper


def get_dashboard():
    return _dashboard


# ---------------------------------------------------------------------------
# Lifespan — initializes everything on server start
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize the full Xeno system on startup, cleanup on shutdown."""
    global _wrapper
    from xeno.config import XenoConfig
    from xeno.agent import XenoAgentWrapper
    from xeno.setup import get_setup_config
    from xeno.key_rotation import init_key_manager

    # Run setup wizard on first start (interactive CLI if TTY, else auto-pick)
    setup = get_setup_config(force_noninteractive=True)
    logger.info(f"Setup: provider={setup.provider}, model={setup.model}, rotation={setup.key_rotation}")

    config = XenoConfig.from_env()
    logger.info("Initializing Xeno agent system...")

    # Initialize key rotation
    if setup.selected_keys:
        for provider, keys in setup.selected_keys.items():
            init_key_manager(
                provider=provider,
                keys=keys,
                strategy=setup.rotation_strategy,
                max_retries=setup.max_retries,
            )

    # Register image provider keys for rotation
    if setup.image_provider and setup.image_api_key:
        img_env_key = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(setup.image_provider, "")
        if img_env_key:
            init_key_manager(
                provider=f"image_{setup.image_provider}",
                keys=[setup.image_api_key],
                strategy="round_robin",
                max_retries=3,
            )
            logger.info(f"Image key rotation registered: {setup.image_provider}")

    _wrapper = XenoAgentWrapper(config=config)

    # Create lightweight LLM (no tools) for fast ack responses
    try:
        from langchain.chat_models import init_chat_model
        provider = config.provider or "deepseek"
        model_name = config.model
        # Strip provider prefix if present (e.g. "deepseek:deepseek-v4-pro" -> "deepseek-v4-pro")
        if ":" in model_name:
            model_name = model_name.split(":", 1)[1]
        # Ollama uses OpenAI-compatible API
        if provider == "ollama":
            provider = "openai"
            os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
            os.environ["OPENAI_API_KEY"] = "ollama"
        _ack_llm = init_chat_model(model_name, model_provider=provider)
        _wrapper._ack_llm = _ack_llm
        logger.info(f"Ack LLM ready: {provider}/{model_name}")
    except Exception as e:
        _wrapper._ack_llm = None
        logger.warning(f"Ack LLM init failed (will use fallback): {e}")

    logger.info("Xeno system ready.")

    # Wire TUI dashboard (may have been created by main() before uvicorn started)
    global _dashboard
    if _dashboard is not None:
        _dashboard.wrapper = _wrapper
        _dashboard.log("Xeno system ready", level="info")
        _dashboard.log(f"Provider: {config.provider}, Model: {config.model}", level="info")
        # Dashboard was already started by main(); no need to start again
    else:
        try:
            from xeno.tui import Dashboard, LogHandler
            _dashboard = Dashboard(wrapper=_wrapper)
            log_handler = LogHandler(_dashboard)
            log_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger("xeno.server").addHandler(log_handler)
            logging.getLogger("xeno.agent").addHandler(log_handler)
            logging.getLogger("xeno.always_on").addHandler(log_handler)
            logging.getLogger("xeno.planner").addHandler(log_handler)
            _dashboard.log("Xeno system ready", level="info")
            _dashboard.log(f"Provider: {config.provider}, Model: {config.model}", level="info")
            _dashboard.start()
        except Exception as e:
            logger.warning(f"Dashboard init failed (using plain logs): {e}")
            _dashboard = None

    # Start background scheduler loop (checks for due tasks every 10s)
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Background scheduler loop started")

    yield

    # Stop scheduler loop
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass

    logger.info("Shutting down Xeno...")
    await _wrapper.shutdown()
    _wrapper = None
    logger.info("Shutdown complete.")


async def _scheduler_loop():
    """Background loop: checks for due tasks every 10s and runs them."""
    import asyncio as _asyncio
    import json as _json
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    results_file = _Path(__file__).parent.parent / "data" / "reminder_results.json"

    while True:
        try:
            await _asyncio.sleep(10)
            w = _wrapper
            if not w or not w.scheduler:
                continue
            due_tasks = w.scheduler.get_due_tasks()
            for task in due_tasks:
                logger.info(f"Scheduler: running due task '{task.name}' ({task.id})")
                result_text = ""
                try:
                    result = await _asyncio.wait_for(w.process(task.prompt), timeout=300.0)
                    result_text = str(result)
                    logger.info(f"Scheduler: task '{task.name}' done: {result_text[:200]}")
                except _asyncio.TimeoutError:
                    result_text = "Task timed out after 300 seconds."
                    logger.warning(f"Scheduler: task '{task.name}' timed out")
                except Exception as e:
                    result_text = f"Error: {e}"
                    logger.error(f"Scheduler: task '{task.name}' failed: {e}")

                w.scheduler.mark_executed(task.id)

                # Store result for client to pick up
                try:
                    results = []
                    if results_file.exists():
                        results = _json.loads(results_file.read_text(encoding="utf-8"))
                    results.append({
                        "task_id": task.id,
                        "task_name": task.name,
                        "prompt": task.prompt,
                        "result": result_text,
                        "executed_at": _dt.now().isoformat(),
                    })
                    results = results[-50:]
                    results_file.write_text(_json.dumps(results, indent=2, default=str), encoding="utf-8")
                except Exception as e:
                    logger.debug(f"Failed to save reminder result: {e}")

        except _asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            await _asyncio.sleep(5)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Xeno Agent Server",
    version="3.0.0",
    description="Fully dynamic AI agent system — agents, tools, MCP, plugins, memory all auto-discovered.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ChatReq(BaseModel):
    message: str
    thread_id: str = "default"
    pattern: Optional[str] = None
    agent_id: Optional[str] = None
    schema_name: Optional[str] = None

class TaskReq(BaseModel):
    prompt: str
    label: str = ""
    priority: str = "normal"
    agent_id: Optional[str] = None
    pattern: Optional[str] = None

class API_TaskReq(BaseModel):
    prompt: str
    label: str = ""
    pattern: Optional[str] = None
    agent_id: Optional[str] = None

class MemoryReq(BaseModel):
    content: str
    memory_type: str = "semantic"
    category: str = "fact"
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5

class ScheduleReq(BaseModel):
    name: str
    prompt: str
    schedule_type: str = "interval"
    schedule_config: dict[str, Any] = Field(default_factory=dict)
    agent_name: Optional[str] = None
    enabled: bool = True

class ScheduleUpdateReq(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[dict[str, Any]] = None
    agent_name: Optional[str] = None
    enabled: Optional[bool] = None

class SkillReq(BaseModel):
    name: str
    description: str
    content: str
    tags: list[str] = Field(default_factory=list)

class ApprovalReq(BaseModel):
    request_id: str
    approved: bool
    notes: str = ""

class ReasonReq(BaseModel):
    task: str
    pattern: Optional[str] = None

class MCPAddReq(BaseModel):
    name: str
    server_type: str = "local"
    command: list[str] = Field(default_factory=list)
    url: str = ""
    env: dict = Field(default_factory=dict)
    enabled: bool = True

class AgentCreateReq(BaseModel):
    name: str
    description: str = ""
    model: str = ""
    tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    system_prompt: str = ""

class ThreadReq(BaseModel):
    title: str = ""
    tags: list[str] = Field(default_factory=list)

class ThreadMsgReq(BaseModel):
    role: str = "user"
    content: str

class TodoCreateReq(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    category: str = ""
    tags: list[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "uptime": time.time()}

@app.get("/health/full")
async def health_full():
    w = get_wrapper()
    return w.get_status()

# ---------------------------------------------------------------------------
# Chat — instant response (quick queries only, heavy → /api/task)
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatReq):
    """Quick chat — uses lightweight ack LLM for instant response.
    Heavy tasks should use /api/task instead."""
    w = get_wrapper()

    # Try fast LLM first for quick queries
    ack_llm = getattr(w, "_ack_llm", None)
    if ack_llm:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            response = await asyncio.wait_for(
                ack_llm.ainvoke([
                    SystemMessage(content=(
                        "You are a helpful AI assistant. Answer the user's message naturally and concisely. "
                        "Keep responses short and conversational. For greetings, greet back warmly."
                    )),
                    HumanMessage(content=req.message[:500]),
                ]),
                timeout=15.0,
            )
            response = response.content if hasattr(response, "content") else str(response)
            result: dict[str, Any] = {"response": response, "thread_id": req.thread_id, "ts": time.time()}
            if req.schema_name:
                ok, parsed = w.schemas.parse_llm_output(req.schema_name, response)
                result["schema_valid"] = ok
                if ok:
                    result["structured"] = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
            return result
        except Exception as e:
            logger.debug(f"Fast LLM failed, falling back to full process(): {e}")

    # Fallback to full agent process (slow)
    try:
        if req.pattern:
            response = await asyncio.wait_for(w.process_with_pattern(req.message, req.pattern), timeout=300.0)
        else:
            response = await asyncio.wait_for(w.process(req.message), timeout=300.0)
    except asyncio.TimeoutError:
        response = "Request timed out after 300 seconds. Try a simpler prompt."
    except Exception as e:
        response = f"Error processing request: {e}"
    result = {"response": response, "thread_id": req.thread_id, "ts": time.time()}
    if req.schema_name:
        ok, parsed = w.schemas.parse_llm_output(req.schema_name, response)
        result["schema_valid"] = ok
        if ok:
            result["structured"] = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
    return result

@app.post("/chat/stream")
async def chat_stream(req: ChatReq):
    w = get_wrapper()
    async def generate():
        yield f"data: {json.dumps({'type': 'start'})}\n\n"
        try:
            if req.pattern:
                response = await w.process_with_pattern(req.message, req.pattern)
            else:
                response = await w.process(req.message)
            for i in range(0, len(response), 60):
                yield f"data: {json.dumps({'type': 'chunk', 'text': response[i:i+60]})}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'type': 'done', 'full': response})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# ---------------------------------------------------------------------------
# Background Tasks — assign infinite concurrent work
# ---------------------------------------------------------------------------

@app.post("/tasks")
async def task_create(req: TaskReq):
    """Spawn a background task. Returns task_id immediately. Poll /tasks/{id} for result."""
    w = get_wrapper()
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    w._bg_tasks[task_id] = {
        "id": task_id, "label": req.label or req.prompt[:60],
        "prompt": req.prompt, "status": "running",
        "agent_id": req.agent_id, "pattern": req.pattern,
        "created": time.time(), "result": None, "error": None,
    }
    asyncio.create_task(_run_bg_task(w, task_id, req.prompt, req.pattern))
    return {"task_id": task_id, "status": "running", "label": req.label or req.prompt[:60]}

async def _run_bg_task(w, task_id: str, prompt: str, pattern: Optional[str]):
    """Execute a background task and store the result."""
    try:
        if pattern:
            result = await w.process_with_pattern(prompt, pattern)
        else:
            result = await w.process(prompt)
        w._bg_tasks[task_id]["result"] = result
        w._bg_tasks[task_id]["status"] = "completed"
        w._bg_tasks[task_id]["completed"] = time.time()
    except Exception as e:
        w._bg_tasks[task_id]["error"] = str(e)
        w._bg_tasks[task_id]["status"] = "failed"
        w._bg_tasks[task_id]["completed"] = time.time()

@app.get("/tasks")
async def task_list(status: Optional[str] = None):
    w = get_wrapper()
    tasks = list(w._bg_tasks.values())
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    return {"tasks": sorted(tasks, key=lambda t: t["created"], reverse=True)}

@app.get("/tasks/{task_id}")
async def task_get(task_id: str):
    w = get_wrapper()
    task = w._bg_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task

@app.delete("/tasks/{task_id}")
async def task_cancel(task_id: str):
    w = get_wrapper()
    task = w._bg_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] == "running":
        task["status"] = "cancelled"
        task["completed"] = time.time()
    return {"status": "cancelled", "id": task_id}

@app.get("/tasks/running/count")
async def task_running_count():
    w = get_wrapper()
    running = sum(1 for t in w._bg_tasks.values() if t["status"] == "running")
    return {"running": running}

# ---------------------------------------------------------------------------
# API Task — agent decides response mode: immediate or background
# ---------------------------------------------------------------------------

MAX_CONCURRENT_TASKS = 8
_api_task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
_priority_queues: dict[str, asyncio.Queue] = {
    "immediate": asyncio.Queue(),
    "background": asyncio.Queue(),
}
_priority_worker_started = False


async def _classify_mode(prompt: str) -> str:
    """Agent decides: 'chat' (instant, no tools), 'quick_task' (tools, fast, no labels), 'background' (labels+queue)."""
    w = get_wrapper()
    ack_llm = getattr(w, "_ack_llm", None)
    if not ack_llm:
        return "quick_task"
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        result = await asyncio.wait_for(
            ack_llm.ainvoke([
                SystemMessage(content=(
                    "Decide how to handle this request. Return ONLY JSON: {\"mode\":\"chat\"|\"quick_task\"|\"background\"}\n\n"
                    "\"chat\": pure conversation — greetings, questions, opinions, explanations, "
                    "sharing info, memory recall. NO tool use needed. Answer in 1-2 sentences.\n"
                    "\"quick_task\": needs tools but fast — scheduling, reminders, quick file ops, "
                    "single tool calls. Agent does the work, user sees result directly.\n"
                    "\"background\": takes noticeable time (10+ seconds) — building projects, "
                    "multi-step research, coding, image gen, browsing, web search, deploying.\n\n"
                    "Examples:\n"
                    "\"hi\" → {\"mode\":\"chat\"}\n"
                    "\"what is python\" → {\"mode\":\"chat\"}\n"
                    "\"remember my favorite color is blue\" → {\"mode\":\"chat\"}\n"
                    "\"remind me to call mom at 5pm\" → {\"mode\":\"quick_task\"}\n"
                    "\"set a timer for 5 minutes\" → {\"mode\":\"quick_task\"}\n"
                    "\"create a file called test.txt\" → {\"mode\":\"quick_task\"}\n"
                    "\"search the web for AI news\" → {\"mode\":\"background\"}\n"
                    "\"build me a portfolio website\" → {\"mode\":\"background\"}\n"
                    "\"generate an image of a cat\" → {\"mode\":\"background\"}\n"
                    "\"research quantum computing\" → {\"mode\":\"background\"}\n\n"
                    "Reply with ONLY the JSON."
                )),
                HumanMessage(content=prompt[:300]),
            ]),
            timeout=10.0,
        )
        raw = (result.content or "").strip()
        if "```" in raw:
            import re
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if m:
                raw = m.group(1)
        parsed = json.loads(raw)
        mode = parsed.get("mode", "quick_task")
        return mode if mode in ("chat", "quick_task", "background") else "quick_task"
    except Exception:
        return "quick_task"


async def _priority_worker():
    """Process background tasks one at a time."""
    global _priority_worker_started
    _priority_worker_started = True
    while True:
        try:
            _, w, task_id, prompt, pattern = await _priority_queues["background"].get()
            w._bg_tasks[task_id]["status"] = "running"
            async with _api_task_semaphore:
                try:
                    if pattern:
                        result = await asyncio.wait_for(w.process_with_pattern(prompt, pattern), timeout=300.0)
                    else:
                        result = await asyncio.wait_for(w.process(prompt), timeout=300.0)
                    final = str(result)
                    w._bg_tasks[task_id]["status"] = "completed"
                    w._bg_tasks[task_id]["final_response"] = final
                    w._bg_tasks[task_id]["result"] = final
                except asyncio.TimeoutError:
                    w._bg_tasks[task_id]["status"] = "failed"
                    w._bg_tasks[task_id]["error"] = "timeout"
                    w._bg_tasks[task_id]["final_response"] = "Task timed out after 300 seconds."
                except Exception as e:
                    w._bg_tasks[task_id]["status"] = "failed"
                    w._bg_tasks[task_id]["error"] = str(e)
                    w._bg_tasks[task_id]["final_response"] = f"Error: {e}"
            w._bg_tasks[task_id]["completed"] = time.time()
        except Exception as e:
            logger.error(f"Priority worker error: {e}")


@app.post("/api/task")
async def api_task_create(req: API_TaskReq):
    """Agent decides: chat (instant ack), quick_task (tools, no labels), background (ack+queue+poll)."""
    global _priority_worker_started
    if not _priority_worker_started:
        asyncio.create_task(_priority_worker())

    w = get_wrapper()
    task_id = f"api_{uuid.uuid4().hex[:8]}"
    mode = await _classify_mode(req.prompt)

    # --- CHAT: instant answer from ack_llm, no tools ---
    if mode == "chat":
        response = "I'm here! How can I help?"
        ack_llm = getattr(w, "_ack_llm", None)
        if ack_llm:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                r = await asyncio.wait_for(
                    ack_llm.ainvoke([
                        SystemMessage(content="You are a helpful assistant. Answer concisely and naturally."),
                        HumanMessage(content=req.prompt[:500]),
                    ]),
                    timeout=15.0,
                )
                response = r.content if hasattr(r, "content") else str(r)
            except Exception:
                pass
        w._bg_tasks[task_id] = {
            "id": task_id, "label": req.label or req.prompt[:60], "prompt": req.prompt,
            "status": "completed", "first_response": response, "final_response": response,
            "created": time.time(), "completed": time.time(), "result": response, "error": None,
        }
        logger.info(f"Task {task_id}: chat -> instant")
        return {"task_id": task_id, "status": "completed", "mode": "chat",
                "first_response": response, "final_response": response}

    # --- QUICK_TASK: full agent inline, user sees result directly (no labels) ---
    if mode == "quick_task":
        try:
            if req.pattern:
                result = await asyncio.wait_for(w.process_with_pattern(req.prompt, req.pattern), timeout=60.0)
            else:
                result = await asyncio.wait_for(w.process(req.prompt), timeout=60.0)
            response = str(result)
            s = "completed"
            err = None
        except asyncio.TimeoutError:
            response = "Request timed out."
            s = "failed"
            err = "timeout"
        except Exception as e:
            response = f"Error: {e}"
            s = "failed"
            err = str(e)
        w._bg_tasks[task_id] = {
            "id": task_id, "label": req.label or req.prompt[:60], "prompt": req.prompt,
            "status": s, "first_response": response, "final_response": response,
            "created": time.time(), "completed": time.time(), "result": response, "error": err,
        }
        logger.info(f"Task {task_id}: quick_task -> {s}")
        return {"task_id": task_id, "status": s, "mode": "quick_task",
                "first_response": response, "final_response": response, "error": err}

    # --- BACKGROUND: ack + queue for long work, labels shown ---
    first = f"Ok, working on: {req.prompt[:120]}..."
    ack_llm = getattr(w, "_ack_llm", None)
    if ack_llm:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            ack_result = await asyncio.wait_for(
                ack_llm.ainvoke([
                    SystemMessage(content="You acknowledge tasks in 1-2 sentences. Be natural."),
                    HumanMessage(content=req.prompt[:300]),
                ]),
                timeout=15.0,
            )
            ack_text = ack_result.content if hasattr(ack_result, "content") else str(ack_result)
            if ack_text and len(ack_text) > 5:
                first = ack_text
        except Exception:
            pass
    w._bg_tasks[task_id] = {
        "id": task_id, "label": req.label or req.prompt[:60], "prompt": req.prompt,
        "status": "accepted", "first_response": first,
        "final_response": None, "created": time.time(), "completed": None,
        "result": None, "error": None,
    }
    _priority_queues["background"].put_nowait(("bg", w, task_id, req.prompt, req.pattern))
    logger.info(f"Task {task_id}: background -> queued")
    return {"task_id": task_id, "status": "accepted", "mode": "background",
            "first_response": first, "poll_url": f"/api/task/{task_id}"}


@app.get("/api/task/{task_id}")
async def api_task_get(task_id: str):
    w = get_wrapper()
    task = w._bg_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {
        "task_id": task["id"], "status": task.get("status", "?"),
        "first_response": task.get("first_response", ""),
        "final_response": task.get("final_response") or task.get("result", ""),
        "error": task.get("error"),
    }

@app.get("/api/tasks")
async def api_task_list(status: Optional[str] = None):
    w = get_wrapper()
    tasks = [
        {"task_id": t["id"], "status": t.get("status", "?"), "label": t.get("label", "")[:60]}
        for t in w._bg_tasks.values()
        if t["id"].startswith("api_") and (status is None or t.get("status") == status)
    ]
    return {"tasks": tasks, "count": len(tasks)}

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@app.post("/memory/store")
async def mem_store(req: MemoryReq):
    w = get_wrapper()
    if req.memory_type == "semantic":
        entry = w.memory.remember_fact(req.content, req.category, req.importance, req.tags)
    else:
        entry = w.memory.record_experience(req.content, req.category, req.importance, req.tags)
    return {"id": entry.id, "type": req.memory_type}

@app.post("/memory/search")
async def mem_search(query: str, limit: int = 10):
    w = get_wrapper()
    results = w.memory.recall(query, limit=limit)
    out = {}
    for k, entries in results.items():
        out[k] = [{"id": e.id, "content": e.content, "strength": round(e.strength(), 3)} for e in entries]
    return {"results": out}

@app.get("/memory/summary")
async def mem_summary():
    w = get_wrapper()
    return {"summary": w.memory.full_summary()}

@app.post("/memory/consolidate")
async def mem_consolidate():
    w = get_wrapper()
    w.memory.consolidate()
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Schedules — full CRUD
# ---------------------------------------------------------------------------

@app.get("/schedules")
async def sched_list():
    w = get_wrapper()
    tasks = w.scheduler.tasks
    from dataclasses import asdict
    return {"schedules": {k: asdict(v) for k, v in tasks.items()}, "count": len(tasks)}

@app.get("/schedules/due")
async def sched_due():
    w = get_wrapper()
    from dataclasses import asdict
    due = w.scheduler.get_due_tasks()
    return {"due": [asdict(t) for t in due], "count": len(due)}

@app.post("/schedules")
async def sched_create(req: ScheduleReq):
    w = get_wrapper()
    result = w.scheduler.create(
        name=req.name,
        prompt=req.prompt,
        schedule_type=req.schedule_type,
        schedule_config=req.schedule_config,
        agent_name=req.agent_name,
    )
    return {"status": "created", "message": result}

@app.get("/schedules/{task_id}")
async def sched_get(task_id: str):
    w = get_wrapper()
    import json as _json
    result = w.scheduler.read(task_id)
    try:
        return _json.loads(result)
    except Exception:
        raise HTTPException(404, result)

@app.put("/schedules/{task_id}")
async def sched_update(task_id: str, req: ScheduleUpdateReq):
    w = get_wrapper()
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    result = w.scheduler.update(task_id, **kwargs)
    if "No schedule" in result:
        raise HTTPException(404, result)
    return {"status": "updated", "message": result}

@app.delete("/schedules/{task_id}")
async def sched_delete(task_id: str):
    w = get_wrapper()
    result = w.scheduler.delete(task_id)
    if "No schedule" in result:
        raise HTTPException(404, result)
    return {"status": "deleted", "message": result}

@app.post("/schedules/{task_id}/enable")
async def sched_enable(task_id: str):
    w = get_wrapper()
    result = w.scheduler.enable(task_id)
    if "No schedule" in result:
        raise HTTPException(404, result)
    return {"status": "enabled", "message": result}

@app.post("/schedules/{task_id}/disable")
async def sched_disable(task_id: str):
    w = get_wrapper()
    result = w.scheduler.disable(task_id)
    if "No schedule" in result:
        raise HTTPException(404, result)
    return {"status": "disabled", "message": result}

@app.post("/schedules/{task_id}/execute")
async def sched_execute(task_id: str):
    w = get_wrapper()
    task = w.scheduler.tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"No schedule with id '{task_id}'")
    w.scheduler.mark_executed(task_id)
    return {"status": "executed", "task_id": task_id, "name": task.name}

# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@app.get("/skills")
async def skills_list():
    w = get_wrapper()
    return {"skills": w.skills.list_skills()}

@app.post("/skills")
async def skills_create(req: SkillReq):
    w = get_wrapper()
    skill = w.skills.create_skill(req.name, req.description, req.content, req.tags)
    return {"name": skill.get("name", req.name)}

# ---------------------------------------------------------------------------
# Todos
# ---------------------------------------------------------------------------

def _tm():
    from xeno.todos import TodoManager
    from xeno.config import XenoConfig
    return TodoManager(XenoConfig.from_env().data_dir / "todos.json")

@app.get("/todos")
async def todos_list(status: Optional[str] = None, priority: Optional[str] = None,
                     category: Optional[str] = None, sort_by: str = "priority"):
    tm = _tm()
    todos = tm.filter(status=status, priority=priority, category=category, limit=50)
    todos = tm.sort(todos, by=sort_by)
    return {"todos": [t.to_dict() for t in todos]}

@app.post("/todos")
async def todos_create(req: TodoCreateReq):
    tm = _tm()
    todo = tm.create(title=req.title, description=req.description, priority=req.priority,
                     category=req.category, tags=req.tags)
    return todo.to_dict()

@app.post("/todos/{todo_id}/complete")
async def todos_complete(todo_id: str):
    tm = _tm()
    todo = tm.complete(todo_id)
    if not todo:
        raise HTTPException(404, "Not found")
    return todo.to_dict()

@app.delete("/todos/{todo_id}")
async def todos_delete(todo_id: str):
    tm = _tm()
    if not tm.delete(todo_id):
        raise HTTPException(404, "Not found")
    return {"status": "deleted"}

# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

@app.get("/approval/pending")
async def approval_pending():
    w = get_wrapper()
    pending = w.approval.get_pending()
    return {"pending": [{"id": r.id, "tool": r.tool_name, "risk": r.risk_level.value} for r in pending]}

@app.post("/approval/respond")
async def approval_respond(req: ApprovalReq):
    w = get_wrapper()
    result = w.approval.approve(req.request_id, notes=req.notes) if req.approved else w.approval.deny(req.request_id, notes=req.notes)
    if not result:
        raise HTTPException(404, "Not found")
    return {"status": result.status.value}

# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------

@app.post("/reason")
async def reason(req: ReasonReq):
    w = get_wrapper()
    trace = w.cognitive.create_trace(req.task)
    response = await w.process_with_pattern(req.task, req.pattern or "adaptive")
    return {"response": response, "trace": trace.to_dict() if trace else None}

# ---------------------------------------------------------------------------
# Dynamic System — Agents
# ---------------------------------------------------------------------------

@app.get("/agents")
async def dyn_agents():
    w = get_wrapper()
    if not w.dynamic:
        return {"agents": []}
    agents = w.dynamic.registry.list_agents()
    return {"agents": [a.to_dict() if hasattr(a, "to_dict") else {"name": str(a)} for a in agents]}

@app.post("/agents")
async def dyn_agent_create(req: AgentCreateReq):
    agent_dir = Path("agents") / req.name.lower().replace(" ", "_").replace("-", "_")
    agent_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nname: {req.name}\nmodel: {req.model or 'deepseek:deepseek-chat'}\ntools: {req.tools}\ntags: {req.tags}\ntemperature: 0.7\nmax_tokens: 4096\nenabled: true\n---\n{req.description}\n"
    (agent_dir / "description.md").write_text(content)
    w = get_wrapper()
    if w.dynamic:
        descriptor = w.dynamic.add_agent_at_runtime(str(agent_dir))
        if descriptor:
            return {"status": "created", "agent": descriptor.to_dict()}
    return {"status": "created", "path": str(agent_dir)}

@app.delete("/agents/{agent_id}")
async def dyn_agent_delete(agent_id: str):
    w = get_wrapper()
    if w.dynamic and w.dynamic.registry.unregister_agent(agent_id):
        return {"status": "deleted"}
    raise HTTPException(404, "Not found")

@app.post("/agents/{agent_id}/reload")
async def dyn_agent_reload(agent_id: str):
    w = get_wrapper()
    if w.dynamic:
        result = w.dynamic.registry.reload_agent(agent_id)
        if result:
            return {"status": "reloaded"}
    raise HTTPException(404, "Not found")

# ---------------------------------------------------------------------------
# 24/7 Always-On Agents — CRUD + start/stop
# ---------------------------------------------------------------------------

@app.get("/always-on")
async def always_on_list():
    """List all 24/7 agents."""
    w = get_wrapper()
    if not w.always_on:
        return {"agents": [], "summary": "Always-on system not initialized"}
    return {"agents": w.always_on.list_agents(), "summary": w.always_on.get_summary()}

@app.post("/always-on")
async def always_on_create(req: dict):
    """Create a new 24/7 agent.

    Body: {name, description, prompt, model, tools, check_interval_minutes,
           restart_policy, max_restarts, custom_tools_dir, auto_start}
    """
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    result = w.always_on.create_agent(
        name=req.get("name", "unnamed"),
        description=req.get("description", ""),
        prompt=req.get("prompt", ""),
        agent_type=req.get("agent_type", "generic"),
        restart_policy=req.get("restart_policy", "with_backoff"),
        max_restarts=req.get("max_restarts", 10),
        check_interval_minutes=req.get("check_interval_minutes", 5),
        model=req.get("model"),
        tools=req.get("tools", []),
        custom_tools_dir=req.get("custom_tools_dir"),
        auto_start=req.get("auto_start", True),
    )
    return {"result": result}

@app.post("/always-on/from-discovery/{agent_id}")
async def always_on_from_discovery(agent_id: str):
    """Start a discovered agent as a 24/7 agent."""
    w = get_wrapper()
    if not w.always_on or not w.dynamic:
        raise HTTPException(503, "System not fully initialized")
    descriptor = w.dynamic.registry.get_agent(agent_id)
    if not descriptor:
        raise HTTPException(404, f"Agent '{agent_id}' not found in discovery")
    result = w.always_on.create_agent_from_descriptor(descriptor, auto_start=True)
    return {"result": result}

@app.post("/always-on/start-all")
async def always_on_start_all():
    """Start all discovered agents with always_on: true."""
    w = get_wrapper()
    if not w.always_on or not w.dynamic:
        raise HTTPException(503, "System not fully initialized")
    results = []
    descriptors = w.dynamic.registry.list_agents(enabled_only=True)
    for desc in descriptors:
        if getattr(desc, "always_on", False):
            result = w.always_on.create_agent_from_descriptor(desc, auto_start=True)
            results.append(result)
    return {"results": results, "count": len(results)}

@app.get("/always-on/{agent_id}")
async def always_on_get(agent_id: str):
    """Get status of a specific 24/7 agent."""
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    status = w.always_on.get_status(agent_id)
    if "not found" in status.lower():
        raise HTTPException(404, status)
    return {"agent": status}

@app.post("/always-on/{agent_id}/start")
async def always_on_start(agent_id: str):
    """Start a 24/7 agent."""
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    result = await w.always_on.start_agent(agent_id)
    return {"result": result}

@app.post("/always-on/{agent_id}/stop")
async def always_on_stop(agent_id: str):
    """Stop a 24/7 agent."""
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    result = await w.always_on.stop_agent(agent_id)
    return {"result": result}

@app.post("/always-on/{agent_id}/restart")
async def always_on_restart(agent_id: str):
    """Restart a 24/7 agent."""
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    result = await w.always_on.restart_agent(agent_id)
    return {"result": result}

@app.delete("/always-on/{agent_id}")
async def always_on_delete(agent_id: str):
    """Delete a 24/7 agent."""
    w = get_wrapper()
    if not w.always_on:
        raise HTTPException(503, "Always-on system not initialized")
    result = w.always_on.delete_agent(agent_id)
    return {"result": result}

@app.get("/always-on/health")
async def always_on_health():
    """Health check all 24/7 agents."""
    w = get_wrapper()
    if not w.always_on:
        return {"health": {}}
    health = await w.always_on.health_check_all()
    return {"health": health}

# ---------------------------------------------------------------------------
# Dynamic System — MCP
# ---------------------------------------------------------------------------

@app.get("/mcp")
async def dyn_mcp_list():
    w = get_wrapper()
    if not w.dynamic:
        return {"servers": []}
    return {"servers": w.dynamic.registry.list_mcp_servers()}

@app.post("/mcp")
async def dyn_mcp_add(req: MCPAddReq):
    w = get_wrapper()
    if not w.dynamic:
        raise HTTPException(503, "Dynamic system unavailable")
    config: dict[str, Any] = {"type": req.server_type, "enabled": req.enabled}
    if req.command:
        config["command"] = req.command
    if req.url:
        config["url"] = req.url
    if req.env:
        config["env"] = req.env
    w.dynamic.add_mcp_server(req.name, **config)
    return {"status": "added", "name": req.name}

@app.delete("/mcp/{name}")
async def dyn_mcp_remove(name: str):
    w = get_wrapper()
    if w.dynamic and w.dynamic.remove_mcp_server(name):
        return {"status": "removed"}
    raise HTTPException(404, "Not found")

# ---------------------------------------------------------------------------
# Dynamic System — Plugins
# ---------------------------------------------------------------------------

@app.get("/plugins")
async def dyn_plugins():
    w = get_wrapper()
    if not w.dynamic:
        return {"plugins": []}
    plugins = w.dynamic.plugin_loader.list_plugins()
    return {"plugins": [p.to_dict() for p in plugins]}

@app.post("/plugins/{name}/reload")
async def dyn_plugin_reload(name: str):
    w = get_wrapper()
    if w.dynamic:
        result = w.dynamic.plugin_loader.reload_plugin(name)
        if result:
            return {"status": "reloaded"}
    raise HTTPException(404, "Not found")

# ---------------------------------------------------------------------------
# Dynamic System — Tools
# ---------------------------------------------------------------------------

@app.get("/tools")
async def dyn_tools():
    w = get_wrapper()
    if not w.dynamic:
        return {"tools": []}
    return {"tools": w.dynamic.registry.list_tools()}

# ---------------------------------------------------------------------------
# Dynamic System — Status / Reload
# ---------------------------------------------------------------------------

@app.post("/dynamic/reload")
async def dyn_reload():
    w = get_wrapper()
    if not w.dynamic:
        return {"error": "unavailable"}
    return {"status": "ok", "counts": w.dynamic.registry.reload_all()}

@app.get("/dynamic/status")
async def dyn_status():
    w = get_wrapper()
    if not w.dynamic:
        return {"running": False}
    return w.dynamic.get_status()

@app.get("/dynamic/health")
async def dyn_health():
    w = get_wrapper()
    if not w.dynamic:
        return {"healthy": False}
    return w.dynamic.registry.check_health()

# ---------------------------------------------------------------------------
# Hooks / Profiles / Threads / Voyager / A2A / Schemas
# ---------------------------------------------------------------------------

@app.get("/hooks")
async def hooks_status():
    return get_wrapper().hooks.stats()

@app.get("/profiles")
async def profiles_list():
    return {"profiles": [p.to_dict() for p in get_wrapper().profiles.list_profiles()]}

@app.get("/profiles/active")
async def profiles_active():
    return get_wrapper().profiles.get_active().to_dict()

@app.get("/threads")
async def threads_list():
    tm = get_wrapper().thread_manager
    threads = tm.list_threads()
    return {"threads": [{"id": t.id, "title": t.title, "msgs": t.message_count} for t in threads]}

@app.post("/threads")
async def threads_create(req: ThreadReq):
    return get_wrapper().thread_manager.create_thread(req.title, req.tags).to_dict()

@app.get("/threads/{thread_id}")
async def threads_get(thread_id: str):
    t = get_wrapper().thread_manager.get_thread(thread_id)
    if not t:
        raise HTTPException(404, "Not found")
    return t.to_dict()

@app.get("/voyager/skills")
async def voyager_list():
    skills = get_wrapper().voyager.search_skills("", limit=50)
    return {"skills": [s.to_dict() for s in skills]}

@app.get("/voyager/stats")
async def voyager_stats():
    return get_wrapper().voyager.get_stats()

@app.get("/a2a/card")
async def a2a_card():
    return get_wrapper().a2a.get_agent_card()

@app.get("/a2a/tasks")
async def a2a_tasks():
    return {"tasks": [t.to_dict() for t in get_wrapper().a2a.list_tasks()]}

@app.get("/schemas")
async def schemas_list():
    return {"schemas": get_wrapper().schemas.list_schemas()}

@app.get("/observability/metrics")
async def obs_metrics():
    return get_wrapper().metrics.summary()

@app.get("/observability/traces")
async def obs_traces():
    return {"traces": get_wrapper().tracer.get_trace_tree()}

@app.get("/checkpoints")
async def cp_list(thread_id: Optional[str] = None):
    cps = get_wrapper().checkpoints.list_checkpoints(thread_id=thread_id)
    return {"checkpoints": [{"id": cp.id, "thread": cp.thread_id, "created": cp.created_at} for cp in cps]}

@app.post("/checkpoints/save")
async def cp_save(thread_id: str = "default"):
    return {"id": get_wrapper().save_checkpoint(thread_id)}

# ---------------------------------------------------------------------------
# Setup & Key Management endpoints
# ---------------------------------------------------------------------------

@app.get("/setup/providers")
async def setup_providers():
    from xeno.setup import api_fetch_providers
    return {"providers": await api_fetch_providers()}

@app.get("/setup/models/{provider}")
async def setup_models(provider: str):
    from xeno.setup import api_fetch_models
    models = await api_fetch_models(provider)
    return {"provider": provider, "models": models, "count": len(models)}

class SetupSaveReq(BaseModel):
    provider: str
    model: str
    small_model: str = ""
    key_rotation: bool = True
    rotation_strategy: str = "round_robin"
    max_retries: int = 3
    selected_keys: Optional[list[str]] = None

@app.post("/setup/save")
async def setup_save(req: SetupSaveReq):
    from xeno.setup import api_save_setup
    config = await api_save_setup(
        provider=req.provider,
        model=req.model,
        small_model=req.small_model,
        key_rotation=req.key_rotation,
        rotation_strategy=req.rotation_strategy,
        max_retries=req.max_retries,
        selected_keys=req.selected_keys,
    )
    return {"status": "saved", "provider": config.provider, "model": config.model}

@app.post("/setup/reset")
async def setup_reset():
    from xeno.setup import SETUP_FILE
    if SETUP_FILE.exists():
        SETUP_FILE.unlink()
    return {"status": "reset", "message": "Setup cleared. Server will run wizard on next start."}

@app.get("/keys/stats")
async def key_stats(provider: Optional[str] = None):
    from xeno.key_rotation import get_key_manager
    km = get_key_manager()
    return km.get_stats(provider)

@app.post("/keys/reset")
async def key_reset(provider: Optional[str] = None):
    from xeno.key_rotation import get_key_manager
    km = get_key_manager()
    km.reset_all(provider)
    return {"status": "reset", "provider": provider or "all"}

@app.post("/keys/strategy")
async def key_set_strategy(strategy: str):
    from xeno.key_rotation import get_key_manager
    km = get_key_manager()
    km.set_strategy(strategy)
    return {"status": "updated", "strategy": strategy}

@app.get("/config")
async def config_info():
    config = get_wrapper().config
    return {
        "model": config.model,
        "small_model": config.small_model,
        "provider": config.provider,
        "key_rotation": config.key_rotation_enabled,
        "rotation_strategy": config.rotation_strategy,
        "max_retries": config.max_retries,
    }

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _kill_port(port: int):
    """Kill any process using the given port (Windows)."""
    import subprocess
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True, timeout=5,
                )
                print(f"Killed old server on port {port} (PID {pid})")
    except Exception:
        pass


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description="Xeno Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI dashboard, use plain logs")
    args = parser.parse_args()

    if args.model:
        import os
        os.environ["XENO_MODEL"] = args.model
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    _kill_port(args.port)

    if args.no_tui:
        # Plain mode -- just run uvicorn
        print(f"Starting Xeno server on {args.host}:{args.port}")
        print(f"Docs: http://{args.host}:{args.port}/docs")
        uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")
    else:
        # TUI mode -- create dashboard BEFORE uvicorn, so lifespan can use it
        import threading

        global _dashboard
        try:
            from xeno.tui import Dashboard, LogHandler
            _dashboard = Dashboard()
            # Install log handler so lifespan logs feed into the dashboard
            log_handler = LogHandler(_dashboard)
            log_handler.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger("xeno.server").addHandler(log_handler)
            logging.getLogger("xeno.agent").addHandler(log_handler)
            logging.getLogger("xeno.always_on").addHandler(log_handler)
            logging.getLogger("xeno.planner").addHandler(log_handler)
            _dashboard.log(f"Server starting on {args.host}:{args.port}", level="info")
            _dashboard.log(f"Docs: http://{args.host}:{args.port}/docs", level="info")
        except Exception as e:
            print(f"Dashboard init failed: {e}")
            _dashboard = None

        def _run_server():
            uvicorn.run(app, host=args.host, port=args.port, log_level="error")

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

        # Give server a moment to initialize
        import time as _time
        _time.sleep(3)

        if _dashboard:
            _dashboard.log("Background scheduler loop started", level="info")
            _dashboard.start()
            try:
                while server_thread.is_alive():
                    _time.sleep(1)
            except KeyboardInterrupt:
                _dashboard.stop()
        else:
            try:
                while server_thread.is_alive():
                    _time.sleep(1)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
