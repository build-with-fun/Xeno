"""A2A v2 client — Agent-to-Agent communication over HTTP."""

from __future__ import annotations
import asyncio, json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

class A2ATaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class A2AAgentCard:
    name: str
    description: str
    version: str = "1.0"
    url: str = ""
    capabilities: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> A2AAgentCard:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class A2ATask:
    id: str
    client_id: str
    agent_id: str
    prompt: str
    state: A2ATaskState = A2ATaskState.SUBMITTED
    progress: float = 0.0
    result: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d

class A2AClient:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None, my_card: Optional[A2AAgentCard] = None):
        self.http = http_client or httpx.AsyncClient(timeout=30.0)
        self.my_card = my_card
        self._discovered: dict[str, A2AAgentCard] = {}
        self._tasks: dict[str, A2ATask] = {}

    async def discover_agent(self, url: str) -> Optional[A2AAgentCard]:
        card_url = url.rstrip("/") + "/.well-known/agent.json"
        try:
            resp = await self.http.get(card_url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            card = A2AAgentCard.from_dict(data)
            self._discovered[url] = card
            logger.info(f"Discovered A2A agent at {url}: {card.name} v{card.version}")
            return card
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                try:
                    alt = url.rstrip("/") + "/a2a/card"
                    resp = await self.http.get(alt, timeout=10.0)
                    resp.raise_for_status()
                    data = resp.json()
                    card = A2AAgentCard.from_dict(data)
                    self._discovered[url] = card
                    return card
                except Exception:
                    pass
            logger.debug(f"A2A discover failed for {url}: {e}")
            return None
        except Exception as e:
            logger.debug(f"A2A discover failed for {url}: {e}")
            return None

    async def delegate_task(self, agent_url: str, prompt: str, task_id: str = "") -> Optional[str]:
        tid = task_id or f"a2a_{uuid.uuid4().hex[:12]}"
        submit_url = agent_url.rstrip("/") + "/a2a/tasks"
        try:
            resp = await self.http.post(
                submit_url,
                json={"id": tid, "prompt": prompt, "client_id": self.my_card.name if self.my_card else "xeno"},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            task = A2ATask(
                id=tid,
                client_id=self.my_card.name if self.my_card else "xeno",
                agent_id=agent_url,
                prompt=prompt,
                state=A2ATaskState(data.get("state", "submitted")),
            )
            self._tasks[tid] = task
            logger.info(f"A2A task {tid} submitted to {agent_url}")
            return tid
        except Exception as e:
            logger.warning(f"A2A delegate_task failed: {e}")
            return None

    async def poll_task(self, task_id: str) -> Optional[A2ATask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        poll_url = task.agent_id.rstrip("/") + f"/a2a/tasks/{task_id}"
        try:
            resp = await self.http.get(poll_url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            task.state = A2ATaskState(data.get("state", "working"))
            task.progress = data.get("progress", task.progress)
            task.result = data.get("result", task.result)
            task.error = data.get("error", task.error)
            if task.state in (A2ATaskState.COMPLETED, A2ATaskState.FAILED):
                task.completed_at = time.time()
            return task
        except Exception as e:
            logger.debug(f"A2A poll task {task_id} failed: {e}")
            return task

    async def delegate_and_wait(self, agent_url: str, prompt: str, poll_interval: float = 1.0, timeout: float = 120.0) -> str:
        tid = await self.delegate_task(agent_url, prompt)
        if not tid:
            return f"Failed to delegate task to {agent_url}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(poll_interval)
            task = await self.poll_task(tid)
            if task is None:
                return "Task lost"
            if task.state == A2ATaskState.COMPLETED:
                return task.result or "Task completed (no result)"
            if task.state == A2ATaskState.FAILED:
                return f"Task failed: {task.error}"
            if task.state == A2ATaskState.CANCELLED:
                return "Task cancelled"
        return f"Task timed out after {timeout}s"

    def list_discovered(self) -> list:
        return list(self._discovered.values())

    def list_tasks(self) -> list:
        return list(self._tasks.values())

    def publish_my_card(self) -> dict:
        return self.my_card.to_dict() if self.my_card else {}

    async def handle_task_request(self, task_data: dict) -> dict:
        tid = task_data.get("id", f"task_{uuid.uuid4().hex[:8]}")
        prompt = task_data.get("prompt", "")
        task = A2ATask(
            id=tid,
            client_id=task_data.get("client_id", "unknown"),
            agent_id="local",
            prompt=prompt,
            state=A2ATaskState.WORKING,
        )
        self._tasks[tid] = task
        asyncio.create_task(self._execute_task(tid, prompt))
        return {"id": tid, "state": "working"}

    async def _execute_task(self, tid: str, prompt: str):
        task = self._tasks.get(tid)
        if not task:
            return
        try:
            from xeno.agent import XenoAgent
            from xeno.config import XenoConfig
            agent = XenoAgent(config=XenoConfig.from_env(), load_mcp=False)
            result = await agent.run(prompt)
            task.result = str(result)[:10000]
            task.state = A2ATaskState.COMPLETED
            task.completed_at = time.time()
        except Exception as e:
            task.error = str(e)
            task.state = A2ATaskState.FAILED
            task.completed_at = time.time()

    def get_task_status(self, tid: str) -> Optional[dict]:
        task = self._tasks.get(tid)
        if not task:
            return None
        return task.to_dict()

    async def close(self):
        await self.http.aclose()
