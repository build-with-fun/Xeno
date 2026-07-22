"""Outbound API: allows external systems to send WhatsApp messages.

This is the flip side of the auto-responder — instead of the bot
replying to incoming messages, external systems (CRM, notification
services, scripts) can proactively send messages to contacts via the
bot's WhatsApp connection.

Messages sent via the outbound API are queued in the scheduler and
sent by the scheduler worker, respecting rate limits and anti-detection
delays.

API endpoints (mounted on the admin FastAPI app):
  POST /api/outbound/send          — Send a single message
  POST /api/outbound/schedule      — Schedule a message for later
  POST /api/outbound/broadcast     — Start a broadcast campaign
  GET  /api/outbound/status/{id}   — Check message/campaign status
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.security.audit_log import audit_logger

logger = get_logger(__name__)


class SendMessageRequest(BaseModel):
    """Request body for POST /api/outbound/send."""
    contact: str = Field(..., description="Contact name or phone")
    text: str = Field(..., description="Message text", max_length=4096)
    delay_seconds: int = Field(0, description="Delay before sending (0 = immediate)")


class ScheduleMessageRequest(BaseModel):
    """Request body for POST /api/outbound/schedule."""
    contact: str
    text: str = Field(..., max_length=4096)
    scheduled_for: datetime = Field(..., description="ISO 8601 datetime")
    recurrence: Optional[str] = Field(None, description="daily|weekly|monthly")


class BroadcastRequest(BaseModel):
    """Request body for POST /api/outbound/broadcast."""
    name: str = Field(..., description="Campaign name")
    template: str = Field(..., description="Message template with {name} placeholder")
    recipients: list[str] = Field(..., description="Contact names")
    variables: Optional[dict] = Field(None, description="Per-recipient variables")
    start_now: bool = Field(True, description="Start sending immediately")


class OutboundAPI:
    """Outbound message API router."""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/outbound", tags=["outbound"])
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.post("/send")
        async def send_message(req: SendMessageRequest):
            """Send a single message immediately (or with a short delay)."""
            from media.whatsapp.scheduler.manager import scheduler
            from datetime import timedelta
            send_at = datetime.utcnow() + timedelta(seconds=req.delay_seconds)
            msg_id = scheduler.schedule(
                contact_name=req.contact, text=req.text, scheduled_for=send_at,
            )
            audit_logger.log(
                actor="outbound_api", action="send_message",
                target=str(msg_id),
                details={"contact": req.contact, "text_preview": req.text[:80]},
            )
            return {"ok": True, "scheduled_id": msg_id, "send_at": send_at.isoformat()}

        @self.router.post("/schedule")
        async def schedule_message(req: ScheduleMessageRequest):
            """Schedule a message for a future time."""
            from media.whatsapp.scheduler.manager import scheduler
            if req.scheduled_for <= datetime.utcnow():
                raise HTTPException(400, "scheduled_for must be in the future")
            msg_id = scheduler.schedule(
                contact_name=req.contact, text=req.text,
                scheduled_for=req.scheduled_for, recurrence=req.recurrence,
            )
            audit_logger.log(
                actor="outbound_api", action="schedule_message",
                target=str(msg_id),
                details={
                    "contact": req.contact,
                    "scheduled_for": req.scheduled_for.isoformat(),
                    "recurrence": req.recurrence,
                },
            )
            return {"ok": True, "scheduled_id": msg_id}

        @self.router.post("/broadcast")
        async def create_broadcast(req: BroadcastRequest):
            """Create and optionally start a broadcast campaign."""
            from media.whatsapp.broadcast.manager import broadcast_manager
            if not req.recipients:
                raise HTTPException(400, "At least one recipient required")
            campaign_id = broadcast_manager.create_campaign(
                name=req.name, template=req.template,
                recipients=req.recipients, variables=req.variables,
            )
            if req.start_now:
                broadcast_manager.start_campaign(campaign_id)
            audit_logger.log(
                actor="outbound_api", action="create_broadcast",
                target=str(campaign_id),
                details={
                    "name": req.name,
                    "recipient_count": len(req.recipients),
                    "started": req.start_now,
                },
            )
            return {
                "ok": True, "campaign_id": campaign_id,
                "recipient_count": len(req.recipients),
            }

        @self.router.get("/status/scheduled/{msg_id}")
        async def scheduled_status(msg_id: int):
            """Check status of a scheduled message."""
            from media.whatsapp.db.repo import ScheduledMessageRepo
            from media.whatsapp.db.database import session_scope
            with session_scope() as s:
                from media.whatsapp.db.models import ScheduledMessage
                msg = s.query(ScheduledMessage).filter(ScheduledMessage.id == msg_id).first()
                if not msg:
                    raise HTTPException(404, "Not found")
                return {
                    "id": msg.id,
                    "contact": msg.contact_name,
                    "status": msg.status,
                    "scheduled_for": msg.scheduled_for.isoformat(),
                    "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
                    "error": msg.error,
                }

        @self.router.get("/status/campaign/{campaign_id}")
        async def campaign_status(campaign_id: int):
            """Check status of a broadcast campaign."""
            from media.whatsapp.broadcast.manager import broadcast_manager
            c = broadcast_manager.get_campaign(campaign_id)
            if not c:
                raise HTTPException(404, "Campaign not found")
            return {
                "id": c.id,
                "name": c.name,
                "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
                "total_recipients": c.total_recipients,
                "sent_count": c.sent_count,
                "failed_count": c.failed_count,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            }

        @self.router.get("/scheduled")
        async def list_scheduled():
            """List all pending scheduled messages."""
            from media.whatsapp.scheduler.manager import scheduler
            items = scheduler.list_pending()
            return {
                "count": len(items),
                "items": [
                    {
                        "id": m.id,
                        "contact": m.contact_name,
                        "text_preview": m.text[:80],
                        "scheduled_for": m.scheduled_for.isoformat(),
                        "recurrence": m.recurrence,
                    }
                    for m in items
                ],
            }

        @self.router.post("/campaign/{campaign_id}/cancel")
        async def cancel_campaign(campaign_id: int):
            """Cancel a running campaign."""
            from media.whatsapp.broadcast.manager import broadcast_manager
            ok = broadcast_manager.cancel_campaign(campaign_id)
            if not ok:
                raise HTTPException(400, "Could not cancel")
            audit_logger.log(
                actor="outbound_api", action="cancel_campaign",
                target=str(campaign_id),
            )
            return {"ok": True}


# Singleton
outbound_api = OutboundAPI()
