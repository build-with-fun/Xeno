"""Xeno Client — CLI and library for communicating with Xeno server.

All requests go through /api/task. The server's agent decides the priority.

Run:
    uv run xeno/client.py "open youtube"
    uv run xeno/client.py "hi"
    uv run xeno/client.py --batch tasks.txt --concurrent 100
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from langchain.chat_models import init_chat_model

logger = logging.getLogger("xeno.client")

_PROVIDER_ENV_MAP = {
    "deepseek": "DEEPSEEK_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "qwen": "QWEN_API_KEY",
    "ollama": "",
}


def get_llm_client(config) -> Any:
    """Create a LangChain chat model from XenoConfig.

    Parses the model string (e.g. ``deepseek:deepseek-chat``) into a provider
    prefix and model name, sets the corresponding API key from the config, and
    returns a LangChain chat model instance.
    """
    model_str = config.model
    provider: str | None = None
    model_name: str = model_str
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)

    # Check if the actual setup provider is Ollama (stored in setup.json provider field)
    is_ollama = getattr(config, 'provider', '') == 'ollama'
    if is_ollama:
        # Override langchain provider to use OpenAI-compatible Ollama API
        provider = "openai"
        os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
        os.environ["OPENAI_API_KEY"] = "ollama"
        if model_name:
            os.environ["OPENAI_MODEL"] = model_name

    # Set API key env var from config (setup.json keys) or environment
    if provider:
        env_var = _PROVIDER_ENV_MAP.get(provider)
        if env_var:
            key_val = config.api_keys.get(env_var) or os.environ.get(env_var)
            if key_val:
                os.environ[env_var] = key_val

    kwargs = {}
    if provider:
        kwargs["model_provider"] = provider

    try:
        llm = init_chat_model(model_name, **kwargs)
        logger.info("LLM client created: %s", model_str)
        return llm
    except Exception as e:
        logger.warning("Failed to create LLM client for %s: %s", model_str, e)
        return None


BASE_URL = "http://localhost:8000"


@dataclass
class TaskResult:
    task_id: str
    first_response: str = ""
    final_response: str = ""
    status: str = "pending"
    priority: str = "normal"
    error: str = ""
    created_at: float = 0.0
    elapsed_seconds: float = 0.0

    @property
    def is_done(self) -> bool:
        return self.status in ("completed", "failed", "timeout")

    @property
    def answer(self) -> str:
        return self.final_response or self.first_response or self.error


class XenoClient:
    """Async client for Xeno server."""

    def __init__(self, base_url: str = BASE_URL, max_concurrent: int = 1000):
        self.base_url = base_url.rstrip("/")
        self.max_concurrent = max_concurrent

    async def send_task(self, prompt: str, label: str = "") -> dict:
        """Send task. Returns full response dict."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/task",
                json={"prompt": prompt, "label": label},
            )
            resp.raise_for_status()
            return resp.json()

    async def poll_task(self, task_id: str, timeout: float = 600.0, interval: float = 0.5) -> TaskResult:
        """Poll until task completes."""
        start = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start < timeout:
                try:
                    resp = await client.get(f"{self.base_url}/api/task/{task_id}")
                    resp.raise_for_status()
                    data = resp.json()
                    status = data.get("status", "unknown")
                    if status in ("completed", "failed"):
                        return TaskResult(
                            task_id=task_id,
                            first_response=data.get("first_response", ""),
                            final_response=data.get("final_response", "") or data.get("result", ""),
                            status=status,
                            error=data.get("error", ""),
                            elapsed_seconds=time.time() - start,
                        )
                except Exception:
                    pass
                await asyncio.sleep(interval)
        return TaskResult(task_id=task_id, status="timeout", error=f"Timed out after {timeout}s")

    async def task(self, prompt: str, label: str = "") -> TaskResult:
        """Full task flow: send, poll if background, return result."""
        data = await self.send_task(prompt, label=label)
        task_id = data.get("task_id", "")
        first = data.get("first_response", "")
        mode = data.get("mode", "chat")
        if mode == "background":
            result = await self.poll_task(task_id)
            result.first_response = first
            return result
        return TaskResult(
            task_id=task_id, first_response=first, final_response=first,
            status="completed", elapsed_seconds=0.0,
        )

    async def run_batch(self, prompts: list[str], max_concurrent: int = 100) -> list[TaskResult]:
        sem = asyncio.Semaphore(min(max_concurrent, self.max_concurrent))

        async def _run_one(idx: int, p: str) -> TaskResult:
            async with sem:
                return await self.task(p, label=f"batch_{idx}")

        return await asyncio.gather(*[_run_one(i, p) for i, p in enumerate(prompts)])


def _print_first(text: str):
    try:
        print(f"\n  [ans before work] {text}\n")
    except UnicodeEncodeError:
        print(f"\n  [ans before work] {text.encode('utf-8', errors='replace').decode('utf-8')}\n")

def _print_final(text: str):
    try:
        print(f"  [ans after work] {text}\n")
    except UnicodeEncodeError:
        print(f"  [ans after work] {text.encode('utf-8', errors='replace').decode('utf-8')}\n")


def _check_reminders(as_json: bool = False):
    from pathlib import Path
    results_file = Path(__file__).parent.parent / "data" / "reminder_results.json"
    if not results_file.exists():
        print("No reminder results yet.")
        return
    results = json.loads(results_file.read_text(encoding="utf-8"))
    if not results:
        print("No reminder results yet.")
        return
    if as_json:
        print(json.dumps(results, indent=2))
    else:
        print(f"\n  Recent reminders ({len(results)} total):\n")
        for r in results[-10:]:
            print(f"  [{r.get('executed_at', '?')}] {r.get('task_name', '?')}")
            print(f"    Prompt: {r.get('prompt', '?')[:80]}")
            print(f"    Result: {r.get('result', '?')[:200]}")
            print()


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    import argparse
    parser = argparse.ArgumentParser(description="Xeno Client")
    parser.add_argument("prompt", nargs="?", help="Task prompt")
    parser.add_argument("--server", "-s", default=BASE_URL, help="Server URL")
    parser.add_argument("--check", action="store_true", help="Check recent reminders")
    parser.add_argument("--batch", "-b", help="File with one prompt per line")
    parser.add_argument("--concurrent", "-c", type=int, default=100, help="Max concurrent")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--timeout", "-t", type=int, default=600, help="Timeout seconds")
    args = parser.parse_args()

    client = XenoClient(base_url=args.server, max_concurrent=args.concurrent)

    if args.check:
        _check_reminders(args.json)
        return

    if args.batch:
        with open(args.batch) as f:
            prompts = [line.strip() for line in f if line.strip()]
        if args.json:
            print(json.dumps({"task": "batch", "count": len(prompts)}))
        results = asyncio.run(client.run_batch(prompts, max_concurrent=args.concurrent))
        if args.json:
            print(json.dumps([{
                "id": r.task_id, "status": r.status, "priority": r.priority,
                "first": r.first_response, "final": r.final_response,
                "elapsed": round(r.elapsed_seconds, 1),
            } for r in results], indent=2))
        else:
            done = sum(1 for r in results if r.status == "completed")
            print(f"\n  {done}/{len(results)} completed\n")
            for r in results:
                print(f"  [{'ok' if r.status=='completed' else 'xx'}] ({r.priority}): {r.answer[:100]}")
        return

    if not args.prompt:
        parser.print_help()
        sys.exit(1)

    # ALL requests go through /api/task — agent decides mode
    data = asyncio.run(client.send_task(args.prompt))
    mode = data.get("mode", "chat")
    task_id = data.get("task_id", "")
    first = data.get("first_response", "")

    if args.json:
        if mode == "background":
            result = asyncio.run(client.poll_task(task_id, timeout=args.timeout))
            data["final_response"] = result.final_response
            data["status"] = result.status
        print(json.dumps(data, indent=2))
    elif mode in ("chat", "quick_task"):
        print(f"\n  {first}\n")
    else:
        _print_first(f"[{task_id}] {first}")
        print(f"  Working...", end="", flush=True)
        result = asyncio.run(client.poll_task(task_id, timeout=args.timeout))
        if result.status == "completed":
            print(f" done ({result.elapsed_seconds:.1f}s)")
            _print_final(result.final_response)
        elif result.status == "failed":
            print(f" failed: {result.error}")
        else:
            print(f" timeout ({args.timeout}s)")


if __name__ == "__main__":
    main()
