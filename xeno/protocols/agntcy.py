"""AGNTCY client — agent directory registration and discovery over HTTP."""

from __future__ import annotations
import asyncio, json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

@dataclass
class AGNTCYAgentRecord:
    id: str
    name: str
    description: str
    version: str = "1.0"
    organization: str = ""
    endpoints: list = field(default_factory=list)
    capabilities: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AGNTCYAgentRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

class AGNTCYClient:
    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        directory_urls: Optional[list[str]] = None,
        local_cache: Optional[Path] = None,
    ):
        self.http = http_client or httpx.AsyncClient(timeout=15.0)
        self.directory_urls = directory_urls or []
        self.local_cache = local_cache
        self._cache: dict[str, AGNTCYAgentRecord] = {}
        self._my_record: Optional[AGNTCYAgentRecord] = None
        if local_cache and local_cache.exists():
            self._load_cache()

    def _load_cache(self):
        try:
            data = json.loads(self.local_cache.read_text(encoding="utf-8"))
            for item in data:
                rec = AGNTCYAgentRecord.from_dict(item)
                self._cache[rec.id] = rec
        except Exception as e:
            logger.warning(f"Failed to load AGNTCY cache: {e}")

    def _save_cache(self):
        if not self.local_cache:
            return
        try:
            self.local_cache.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self._cache.values()]
            self.local_cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save AGNTCY cache: {e}")

    async def register(self, record: AGNTCYAgentRecord) -> bool:
        self._my_record = record
        self._cache[record.id] = record
        self._save_cache()
        success = True
        for directory_url in self.directory_urls:
            try:
                reg_url = directory_url.rstrip("/") + "/agents"
                resp = await self.http.post(reg_url, json=record.to_dict(), timeout=10.0)
                resp.raise_for_status()
                logger.info(f"Registered with AGNTCY directory {directory_url}")
            except Exception as e:
                logger.warning(f"AGNTCY register with {directory_url} failed: {e}")
                success = False
        return success

    async def discover(self, query: str = "", tags: Optional[list[str]] = None) -> list[AGNTCYAgentRecord]:
        results: dict[str, AGNTCYAgentRecord] = {}
        for directory_url in self.directory_urls:
            try:
                search_url = directory_url.rstrip("/") + "/agents"
                params = {}
                if query:
                    params["query"] = query
                if tags:
                    params["tags"] = ",".join(tags)
                resp = await self.http.get(search_url, params=params, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
                agents = data if isinstance(data, list) else data.get("agents", data.get("results", []))
                for item in agents:
                    rec = AGNTCYAgentRecord.from_dict(item) if isinstance(item, dict) else item
                    if hasattr(rec, "id"):
                        results[rec.id] = rec
                logger.info(f"Discovered {len(agents)} agents from {directory_url}")
            except Exception as e:
                logger.debug(f"AGNTCY discover from {directory_url} failed: {e}")
                for cached in self._cache.values():
                    if (not query or query.lower() in cached.name.lower() or query.lower() in cached.description.lower()):
                        results[cached.id] = cached
        return list(results.values())

    async def heartbeat(self, directory_url: str) -> bool:
        if not self._my_record:
            return False
        try:
            hb_url = directory_url.rstrip("/") + f"/agents/{self._my_record.id}/heartbeat"
            resp = await self.http.post(hb_url, timeout=10.0)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"AGNTCY heartbeat to {directory_url} failed: {e}")
            return False

    async def start_heartbeat_loop(self, directory_url: str, interval: float = 60.0):
        while True:
            try:
                await asyncio.sleep(interval)
                await self.heartbeat(directory_url)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def list_cached(self) -> list[AGNTCYAgentRecord]:
        return list(self._cache.values())

    def get_record(self, agent_id: str) -> Optional[AGNTCYAgentRecord]:
        return self._cache.get(agent_id)

    def set_my_record(self, record: AGNTCYAgentRecord):
        self._my_record = record
        self._cache[record.id] = record
        self._save_cache()

    async def close(self):
        await self.http.aclose()
