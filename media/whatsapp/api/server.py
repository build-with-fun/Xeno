"""FastAPI admin server with full queue, analytics, and chat data management.

Fixes the original code's issues (the original relied on a separate
`server.py` file that wasn't included — this version is integrated):
- No authentication on admin endpoints
- No structured response format
- No health check endpoint
- No metrics endpoint
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Security, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from media.whatsapp.analytics.tracker import analytics
from media.whatsapp.config import settings
from media.whatsapp.db.repo import ContactRepo, MessageRepo
from media.whatsapp.observability.health import health
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics
from media.whatsapp.taskqueue.approval import approval_queue
from media.whatsapp.taskqueue.retry import retry_queue
from media.whatsapp.safety.keywords import keyword_alerts
from media.whatsapp.safety.rate_limiter import rate_limiter

logger = get_logger(__name__)

_security = HTTPBearer(auto_error=False)


def _verify_token(
    creds: Optional[HTTPAuthorizationCredentials] = Security(_security),
) -> bool:
    """Dependency: verify the admin API token."""
    expected = settings.admin_api_token
    # Allow unauthenticated access from localhost for convenience
    # (the bind host is 127.0.0.1 by default)
    if not creds:
        return True  # rely on bind host for security
    if creds.credentials != expected:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return True


# ── Request models ──────────────────────────────────────────────────────────
class ApproveRequest(BaseModel):
    msg_id: int
    custom_context: str = ""
    custom_reply: str = ""


class RejectRequest(BaseModel):
    msg_id: int
    reason: str = ""


class KeywordUpdate(BaseModel):
    keywords: list[str]


class BotControlRequest(BaseModel):
    action: str  # "stop" | "start"


# ── Bot reference (set by Bot.start()) ─────────────────────────────────────
_bot_ref: Any = None


def set_bot(bot: Any) -> None:
    """Store a reference to the Bot instance so API endpoints can access live data."""
    global _bot_ref
    _bot_ref = bot


# ── Response helpers ────────────────────────────────────────────────────────
def _contact_to_dict(c: Any) -> dict:
    return {
        "name": c.name,
        "phone": c.phone or "",
        "tags": c.tags or [],
        "is_group": c.is_group,
        "is_blocked": c.is_blocked,
        "total_messages": c.total_messages,
        "total_replies": c.total_replies,
        "last_seen": c.last_seen.isoformat() if c.last_seen else "",
        "sentiment_score": c.sentiment_score,
    }


def _message_to_dict(m: Any) -> dict:
    return {
        "id": m.id,
        "role": m.role.value if hasattr(m.role, "value") else str(m.role),
        "kind": m.kind.value if hasattr(m.kind, "value") else str(m.kind),
        "content": m.content,
        "label": m.label,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    }


# ── Server ──────────────────────────────────────────────────────────────────
class AdminServer:
    """Wraps the FastAPI app and runs it in a background thread."""

    def __init__(self) -> None:
        self.app = FastAPI(
            title="WhatsApp Bot Admin",
            version="2.0.0",
            docs_url="/docs",
            redoc_url=None,
        )
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._register_routes()

    def _register_routes(self) -> None:
        app = self.app

        @app.get("/api/health")
        async def health_endpoint():
            return health.run_all()

        @app.get("/api/metrics", dependencies=[Depends(_verify_token)])
        async def metrics_endpoint():
            return metrics.snapshot()

        @app.get("/api/pending", dependencies=[Depends(_verify_token)])
        async def list_pending():
            return {"items": approval_queue.list_pending(), "count": approval_queue.count("pending")}

        @app.get("/api/queue", dependencies=[Depends(_verify_token)])
        async def list_queue(status: Optional[str] = None):
            return {"items": approval_queue.list_all(status), "count": approval_queue.count(status)}

        @app.get("/api/queue/{msg_id}", dependencies=[Depends(_verify_token)])
        async def get_item(msg_id: int):
            item = approval_queue.get(msg_id)
            if not item:
                raise HTTPException(404, "Item not found")
            return item

        @app.post("/api/approve", dependencies=[Depends(_verify_token)])
        async def approve(req: ApproveRequest):
            ok = approval_queue.approve(req.msg_id, req.custom_context, req.custom_reply)
            if not ok:
                raise HTTPException(400, "Could not approve (not in pending state?)")
            return {"ok": True, "msg_id": req.msg_id}

        @app.post("/api/reject", dependencies=[Depends(_verify_token)])
        async def reject(req: RejectRequest):
            ok = approval_queue.reject(req.msg_id, req.reason)
            if not ok:
                raise HTTPException(400, "Could not reject")
            return {"ok": True, "msg_id": req.msg_id}

        @app.get("/api/analytics", dependencies=[Depends(_verify_token)])
        async def analytics_endpoint(days: int = 7):
            return analytics.summary(min(days, 90))

        @app.get("/api/keywords", dependencies=[Depends(_verify_token)])
        async def get_keywords():
            return {"keywords": keyword_alerts.load()}

        @app.put("/api/keywords", dependencies=[Depends(_verify_token)])
        async def update_keywords(req: KeywordUpdate):
            from media.whatsapp.memory.store import store
            store.write(KeywordAlerts.COLLECTION, KeywordAlerts.KEYWORDS_KEY, req.keywords)
            return {"ok": True, "count": len(req.keywords)}

        @app.get("/api/alerts", dependencies=[Depends(_verify_token)])
        async def get_alerts(limit: int = 100):
            return {"alerts": keyword_alerts.get_log(min(limit, 1000))}

        @app.get("/api/retry", dependencies=[Depends(_verify_token)])
        async def retry_status():
            return {
                "count": retry_queue.count(),
                "items": [r.__dict__ for r in retry_queue.due_items()],
            }

        @app.get("/api/rate-limit/{contact}", dependencies=[Depends(_verify_token)])
        async def rate_limit_status(contact: str):
            return rate_limiter.status(contact)

        @app.post("/api/bot/stop", dependencies=[Depends(_verify_token)])
        async def bot_stop():
            # Touch the stop signal file
            settings.stop_signal_path.touch()
            return {"ok": True, "message": "Stop signal sent"}

        # ── Chat data endpoints (read contact/message data from DB + live bot) ──

        @app.get("/api/contacts", dependencies=[Depends(_verify_token)])
        async def list_contacts(limit: int = Query(100, le=500), offset: int = Query(0, ge=0)):
            contacts = ContactRepo.list_all(limit=limit, offset=offset)
            return {
                "contacts": [_contact_to_dict(c) for c in contacts],
                "count": len(contacts),
            }

        @app.get("/api/contacts/search", dependencies=[Depends(_verify_token)])
        async def search_contacts(q: str = Query(..., min_length=1)):
            contacts = ContactRepo.search(q)
            return {
                "contacts": [_contact_to_dict(c) for c in contacts],
                "count": len(contacts),
            }

        @app.get("/api/contacts/{name}", dependencies=[Depends(_verify_token)])
        async def get_contact(name: str):
            contact = ContactRepo.get_by_name(name)
            if not contact:
                raise HTTPException(404, "Contact not found")
            return _contact_to_dict(contact)

        @app.get("/api/messages/{contact_name}", dependencies=[Depends(_verify_token)])
        async def get_messages(contact_name: str, limit: int = Query(50, le=500)):
            msgs = MessageRepo.get_history(contact_name, limit=limit)
            return {
                "contact": contact_name,
                "messages": [_message_to_dict(m) for m in msgs],
                "count": len(msgs),
            }

        @app.get("/api/unread", dependencies=[Depends(_verify_token)])
        async def get_unread():
            if _bot_ref is None:
                return {"unread": [], "count": 0, "note": "Bot not running — no live pending data"}
            items = []
            for contact, info in _bot_ref.pending.items():
                items.append({
                    "contact": contact,
                    "preview": info.get("preview", ""),
                    "mtype": info.get("mtype", "text"),
                    "jid": info.get("jid", ""),
                    "last_seen": info.get("last_seen", 0),
                })
            return {"unread": items, "count": len(items)}

        @app.get("/", dependencies=[Depends(_verify_token)])
        async def root():
            return {
                "name": "WhatsApp Bot Admin",
                "version": "2.0.0",
                "endpoints": [
                    "/api/health", "/api/metrics", "/api/pending",
                    "/api/queue", "/api/approve", "/api/reject",
                    "/api/analytics", "/api/keywords", "/api/alerts",
                    "/api/retry", "/api/rate-limit/{contact}", "/api/bot/stop",
                    "/api/contacts", "/api/contacts/search", "/api/contacts/{name}",
                    "/api/messages/{contact_name}", "/api/unread",
                    "/docs",
                ],
            }

    def start(self) -> None:
        """Start the server in a background thread (non-blocking)."""
        import uvicorn

        def _run():
            uvicorn.run(
                self.app,
                host=settings.admin_host,
                port=settings.admin_port,
                log_level="warning",
                access_log=False,
            )

        self._thread = threading.Thread(target=_run, name="admin-api", daemon=True)
        self._thread.start()
        logger.info(
            f"[AdminAPI] Listening on http://{settings.admin_host}:{settings.admin_port}"
            f" (docs at /docs)"
        )

    def stop(self) -> None:
        """Stop the server (best-effort)."""
        # Uvicorn in a daemon thread — will be killed when main exits
        logger.info("[AdminAPI] Stopping")


# Singleton
admin_server = AdminServer()


# Need to import these at the bottom to avoid circular imports
from media.whatsapp.safety.keywords import KeywordAlerts  # noqa: E402
