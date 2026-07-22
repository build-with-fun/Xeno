"""UMP — Universal Memory Protocol with HTTP remote access."""

from __future__ import annotations
import asyncio, json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

class UMPPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"

@dataclass
class UMPGrant:
    id: str
    grantor: str
    grantee: str
    permission: UMPPermission = UMPPermission.READ
    tier_scope: list = field(default_factory=lambda: ["semantic"])
    ttl_seconds: int = 0
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        d = asdict(self)
        d["permission"] = self.permission.value
        return d

class UMPAccessController:
    def __init__(self, my_agent_id: str, grants_file: Optional[Path] = None):
        self.my_id = my_agent_id
        self.grants_file = grants_file
        self._grants: dict[str, UMPGrant] = {}
        if grants_file and grants_file.exists():
            self._load_grants()

    def _load_grants(self):
        try:
            data = json.loads(self.grants_file.read_text(encoding="utf-8"))
            for item in data:
                g = UMPGrant(**item)
                self._grants[g.id] = g
        except Exception as e:
            logger.warning(f"Failed to load UMP grants: {e}")

    def _save_grants(self):
        if not self.grants_file:
            return
        try:
            self.grants_file.parent.mkdir(parents=True, exist_ok=True)
            data = [g.to_dict() for g in self._grants.values()]
            self.grants_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save UMP grants: {e}")

    def grant(self, grantee: str, permission: UMPPermission = UMPPermission.READ, **kw) -> UMPGrant:
        ttl = kw.pop("ttl_seconds", 0)
        g = UMPGrant(
            id=f"grant_{uuid.uuid4().hex[:8]}",
            grantor=self.my_id,
            grantee=grantee,
            permission=permission,
            ttl_seconds=ttl,
            expires_at=(time.time() + ttl) if ttl > 0 else 0,
            **kw,
        )
        self._grants[g.id] = g
        self._save_grants()
        return g

    def revoke(self, grant_id: str) -> bool:
        if grant_id in self._grants:
            del self._grants[grant_id]
            self._save_grants()
            return True
        return False

    def check_access(self, agent_id: str, permission: UMPPermission, tier: str = "semantic") -> tuple[bool, str]:
        for g in self._grants.values():
            if g.is_expired():
                continue
            if g.grantee == agent_id and g.permission in (permission, UMPPermission.READ_WRITE):
                if not g.tier_scope or tier in g.tier_scope:
                    return True, g.id
        return False, "no grant"

    def list_grants(self) -> list:
        return [g.to_dict() for g in self._grants.values() if not g.is_expired()]

    def list_grants_for(self, agent_id: str) -> list:
        return [g.to_dict() for g in self._grants.values() if g.grantee == agent_id and not g.is_expired()]

class UMPClient:
    def __init__(self, my_agent_id: str, http_client: Optional[httpx.AsyncClient] = None):
        self.my_id = my_agent_id
        self.http = http_client or httpx.AsyncClient(timeout=15.0)
        self._remote_memory: dict[str, str] = {}

    async def read(self, url: str, query: str, tier: str = "semantic") -> dict:
        read_url = url.rstrip("/") + "/ump/read"
        try:
            resp = await self.http.post(
                read_url,
                json={"agent_id": self.my_id, "query": query, "tier": tier},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return {"error": "access_denied", "results": []}
            return {"error": str(e), "results": []}
        except Exception as e:
            logger.debug(f"UMP read from {url} failed: {e}")
            return {"error": str(e), "results": []}

    async def write(self, url: str, content: str, tier: str = "semantic", tags: Optional[list[str]] = None) -> dict:
        write_url = url.rstrip("/") + "/ump/write"
        try:
            resp = await self.http.post(
                write_url,
                json={"agent_id": self.my_id, "content": content, "tier": tier, "tags": tags or []},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return {"success": False, "error": "access_denied"}
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.debug(f"UMP write to {url} failed: {e}")
            return {"success": False, "error": str(e)}

    async def request_grant(self, url: str, permission: str = "read", reason: str = "") -> dict:
        grant_url = url.rstrip("/") + "/ump/request_grant"
        try:
            resp = await self.http.post(
                grant_url,
                json={"agent_id": self.my_id, "permission": permission, "reason": reason},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        await self.http.aclose()
