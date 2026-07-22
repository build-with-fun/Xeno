"""Repository pattern: data access layer for each model.

Provides a clean API for database operations, hiding SQLAlchemy details
from the rest of the codebase.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import desc, func, select, update, delete
from sqlalchemy.orm import Session

from .database import session_scope
from .models import (
    Contact, Message, Approval, RetryItem, AnalyticsEvent,
    ScheduledMessage, BroadcastCampaign, BroadcastRecipient,
    KnowledgeChunk, AuditLog, PluginState,
    ApprovalStatus, CampaignStatus, MessageRole, MessageKind, Sentiment,
)


class ContactRepo:
    """Contact data access."""

    @staticmethod
    def get_or_create(name: str, phone: str = None) -> Contact:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact is None:
                contact = Contact(name=name, phone=phone)
                s.add(contact)
                s.flush()
            else:
                contact.last_seen = datetime.utcnow()
                if phone and not contact.phone:
                    contact.phone = phone
            s.refresh(contact)
            # Detach so it's usable outside the session
            s.expunge(contact)
            return contact

    @staticmethod
    def get_by_name(name: str) -> Optional[Contact]:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact:
                s.expunge(contact)
            return contact

    @staticmethod
    def add_tag(name: str, tag: str) -> None:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact:
                tags = contact.tags or []
                if tag not in tags:
                    tags.append(tag)
                    contact.tags = tags

    @staticmethod
    def update_sentiment(name: str, score: float, sentiment: Sentiment) -> None:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact:
                # Running average: weight new score at 30%
                contact.sentiment_score = (
                    0.7 * contact.sentiment_score + 0.3 * score
                )
                contact.total_messages += 1

    @staticmethod
    def increment_reply_count(name: str) -> None:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact:
                contact.total_replies += 1

    @staticmethod
    def block(name: str) -> None:
        with session_scope() as s:
            contact = s.query(Contact).filter(Contact.name == name).first()
            if contact:
                contact.is_blocked = True

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> list[Contact]:
        with session_scope() as s:
            contacts = (
                s.query(Contact)
                .order_by(desc(Contact.last_seen))
                .limit(limit).offset(offset).all()
            )
            for c in contacts:
                s.expunge(c)
            return contacts

    @staticmethod
    def search(query: str) -> list[Contact]:
        with session_scope() as s:
            contacts = (
                s.query(Contact)
                .filter(Contact.name.ilike(f"%{query}%"))
                .limit(50).all()
            )
            for c in contacts:
                s.expunge(c)
            return contacts


class MessageRepo:
    """Message data access."""

    @staticmethod
    def add(
        contact_name: str, role: MessageRole, content: str,
        kind: MessageKind = MessageKind.TEXT, label: str = "Text",
        whatsapp_msg_id: str = None, provider: str = None,
        sentiment: Sentiment = None, sentiment_score: float = None,
        is_spam: bool = False, spam_score: float = 0.0,
    ) -> Message:
        contact = ContactRepo.get_or_create(contact_name)
        with session_scope() as s:
            msg = Message(
                contact_id=contact.id, role=role, kind=kind, content=content,
                label=label, whatsapp_msg_id=whatsapp_msg_id, ai_provider=provider,
                sentiment=sentiment, sentiment_score=sentiment_score,
                is_spam=is_spam, spam_score=spam_score,
            )
            s.add(msg)
            s.flush()
            s.refresh(msg)
            s.expunge(msg)
            return msg

    @staticmethod
    def get_history(contact_name: str, limit: int = 100) -> list[Message]:
        contact = ContactRepo.get_by_name(contact_name)
        if not contact:
            return []
        with session_scope() as s:
            msgs = (
                s.query(Message)
                .filter(Message.contact_id == contact.id)
                .order_by(desc(Message.created_at))
                .limit(limit).all()
            )
            msgs.reverse()  # oldest first
            for m in msgs:
                s.expunge(m)
            return msgs

    @staticmethod
    def get_since(contact_name: str, since: datetime) -> list[Message]:
        contact = ContactRepo.get_by_name(contact_name)
        if not contact:
            return []
        with session_scope() as s:
            msgs = (
                s.query(Message)
                .filter(Message.contact_id == contact.id, Message.created_at >= since)
                .order_by(Message.created_at).all()
            )
            for m in msgs:
                s.expunge(m)
            return msgs

    @staticmethod
    def count_today() -> dict:
        """Return message counts for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        with session_scope() as s:
            received = s.query(Message).filter(
                Message.role == MessageRole.USER,
                Message.created_at >= today_start,
            ).count()
            sent = s.query(Message).filter(
                Message.role == MessageRole.ASSISTANT,
                Message.created_at >= today_start,
            ).count()
            return {"received": received, "sent": sent}


class ApprovalRepo:
    """Approval queue data access."""

    @staticmethod
    def add(msg_id: int, contact_name: str, messages: list, decision: dict) -> Approval:
        with session_scope() as s:
            approval = Approval(
                msg_id=msg_id, contact_name=contact_name,
                messages=messages, decision=decision,
            )
            s.add(approval)
            s.flush()
            s.refresh(approval)
            s.expunge(approval)
            return approval

    @staticmethod
    def get(msg_id: int) -> Optional[Approval]:
        with session_scope() as s:
            a = s.query(Approval).filter(Approval.msg_id == msg_id).first()
            if a:
                s.expunge(a)
            return a

    @staticmethod
    def list_by_status(status: ApprovalStatus, limit: int = 100) -> list[Approval]:
        with session_scope() as s:
            items = (
                s.query(Approval)
                .filter(Approval.status == status)
                .order_by(desc(Approval.created_at))
                .limit(limit).all()
            )
            for i in items:
                s.expunge(i)
            return items

    @staticmethod
    def update_status(msg_id: int, status: ApprovalStatus, **kwargs) -> bool:
        with session_scope() as s:
            a = s.query(Approval).filter(Approval.msg_id == msg_id).first()
            if not a:
                return False
            a.status = status
            for k, v in kwargs.items():
                if hasattr(a, k):
                    setattr(a, k, v)
            return True

    @staticmethod
    def delete(msg_id: int) -> bool:
        with session_scope() as s:
            a = s.query(Approval).filter(Approval.msg_id == msg_id).first()
            if a:
                s.delete(a)
                return True
            return False

    @staticmethod
    def count(status: ApprovalStatus = None) -> int:
        with session_scope() as s:
            q = s.query(Approval)
            if status:
                q = q.filter(Approval.status == status)
            return q.count()


class AnalyticsRepo:
    """Analytics event data access."""

    @staticmethod
    def record(event_type: str, contact_name: str = None, provider: str = None, extra: dict = None) -> None:
        with session_scope() as s:
            event = AnalyticsEvent(
                event_type=event_type, contact_name=contact_name,
                provider=provider, extra=extra,
            )
            s.add(event)

    @staticmethod
    def count_since(event_type: str, since: datetime) -> int:
        with session_scope() as s:
            return s.query(AnalyticsEvent).filter(
                AnalyticsEvent.event_type == event_type,
                AnalyticsEvent.created_at >= since,
            ).count()

    @staticmethod
    def summary(days: int = 7) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        with session_scope() as s:
            events = s.query(AnalyticsEvent).filter(
                AnalyticsEvent.created_at >= since
            ).all()
            summary = {}
            for e in events:
                key = e.event_type
                summary[key] = summary.get(key, 0) + 1
            # Provider usage
            provider_usage = {}
            for e in events:
                if e.provider:
                    provider_usage[e.provider] = provider_usage.get(e.provider, 0) + 1
            return {
                "days": days,
                "total_events": len(events),
                "by_type": summary,
                "by_provider": provider_usage,
            }


class ScheduledMessageRepo:
    """Scheduled message data access."""

    @staticmethod
    def schedule(contact_name: str, text: str, scheduled_for: datetime,
                 recurrence: str = None) -> ScheduledMessage:
        with session_scope() as s:
            msg = ScheduledMessage(
                contact_name=contact_name, text=text,
                scheduled_for=scheduled_for, recurrence=recurrence,
            )
            s.add(msg)
            s.flush()
            s.refresh(msg)
            s.expunge(msg)
            return msg

    @staticmethod
    def get_due() -> list[ScheduledMessage]:
        now = datetime.utcnow()
        with session_scope() as s:
            msgs = (
                s.query(ScheduledMessage)
                .filter(
                    ScheduledMessage.status == "pending",
                    ScheduledMessage.scheduled_for <= now,
                )
                .order_by(ScheduledMessage.scheduled_for).all()
            )
            for m in msgs:
                s.expunge(m)
            return msgs

    @staticmethod
    def mark_sent(msg_id: int) -> None:
        with session_scope() as s:
            msg = s.query(ScheduledMessage).filter(ScheduledMessage.id == msg_id).first()
            if msg:
                msg.status = "sent"
                msg.sent_at = datetime.utcnow()
                # Handle recurrence
                if msg.recurrence == "daily":
                    new_msg = ScheduledMessage(
                        contact_name=msg.contact_name, text=msg.text,
                        scheduled_for=msg.scheduled_for + timedelta(days=1),
                        recurrence="daily",
                    )
                    s.add(new_msg)
                elif msg.recurrence == "weekly":
                    new_msg = ScheduledMessage(
                        contact_name=msg.contact_name, text=msg.text,
                        scheduled_for=msg.scheduled_for + timedelta(weeks=1),
                        recurrence="weekly",
                    )
                    s.add(new_msg)

    @staticmethod
    def cancel(msg_id: int) -> bool:
        with session_scope() as s:
            msg = s.query(ScheduledMessage).filter(ScheduledMessage.id == msg_id).first()
            if msg and msg.status == "pending":
                msg.status = "cancelled"
                return True
            return False

    @staticmethod
    def list_pending() -> list[ScheduledMessage]:
        with session_scope() as s:
            msgs = (
                s.query(ScheduledMessage)
                .filter(ScheduledMessage.status == "pending")
                .order_by(ScheduledMessage.scheduled_for).all()
            )
            for m in msgs:
                s.expunge(m)
            return msgs


class BroadcastRepo:
    """Broadcast campaign data access."""

    @staticmethod
    def create_campaign(name: str, template: str, recipients: list[str],
                        variables: dict = None) -> BroadcastCampaign:
        with session_scope() as s:
            campaign = BroadcastCampaign(
                name=name, template=template, variables=variables,
                total_recipients=len(recipients),
            )
            s.add(campaign)
            s.flush()
            for r in recipients:
                personalized = template
                if variables and r in variables:
                    for k, v in variables[r].items():
                        personalized = personalized.replace(f"{{{k}}}", str(v))
                personalized = personalized.replace("{name}", r)
                recipient = BroadcastRecipient(
                    campaign_id=campaign.id, contact_name=r,
                    personalized_text=personalized,
                )
                s.add(recipient)
            s.refresh(campaign)
            s.expunge(campaign)
            return campaign

    @staticmethod
    def get(campaign_id: int) -> Optional[BroadcastCampaign]:
        with session_scope() as s:
            c = s.query(BroadcastCampaign).filter(BroadcastCampaign.id == campaign_id).first()
            if c:
                s.expunge(c)
            return c

    @staticmethod
    def list_campaigns(status: CampaignStatus = None) -> list[BroadcastCampaign]:
        with session_scope() as s:
            q = s.query(BroadcastCampaign)
            if status:
                q = q.filter(BroadcastCampaign.status == status)
            campaigns = q.order_by(desc(BroadcastCampaign.created_at)).all()
            for c in campaigns:
                s.expunge(c)
            return campaigns

    @staticmethod
    def get_pending_recipients(campaign_id: int) -> list[BroadcastRecipient]:
        with session_scope() as s:
            recipients = (
                s.query(BroadcastRecipient)
                .filter(
                    BroadcastRecipient.campaign_id == campaign_id,
                    BroadcastRecipient.status == "pending",
                ).all()
            )
            for r in recipients:
                s.expunge(r)
            return recipients

    @staticmethod
    def mark_recipient_sent(recipient_id: int) -> None:
        with session_scope() as s:
            r = s.query(BroadcastRecipient).filter(BroadcastRecipient.id == recipient_id).first()
            if r:
                r.status = "sent"
                r.sent_at = datetime.utcnow()
                # Update campaign counters
                c = s.query(BroadcastCampaign).filter(BroadcastCampaign.id == r.campaign_id).first()
                if c:
                    c.sent_count += 1

    @staticmethod
    def mark_recipient_failed(recipient_id: int, error: str) -> None:
        with session_scope() as s:
            r = s.query(BroadcastRecipient).filter(BroadcastRecipient.id == recipient_id).first()
            if r:
                r.status = "failed"
                r.error = error[:500]
                c = s.query(BroadcastCampaign).filter(BroadcastCampaign.id == r.campaign_id).first()
                if c:
                    c.failed_count += 1

    @staticmethod
    def update_campaign_status(campaign_id: int, status: CampaignStatus) -> None:
        with session_scope() as s:
            c = s.query(BroadcastCampaign).filter(BroadcastCampaign.id == campaign_id).first()
            if c:
                c.status = status
                if status == CampaignStatus.RUNNING:
                    c.started_at = datetime.utcnow()
                elif status == CampaignStatus.COMPLETED:
                    c.completed_at = datetime.utcnow()


class KnowledgeRepo:
    """RAG knowledge base data access."""

    @staticmethod
    def add_chunk(source: str, chunk_index: int, text: str,
                  embedding: bytes = None, metadata: dict = None) -> None:
        with session_scope() as s:
            chunk = KnowledgeChunk(
                source=source, chunk_index=chunk_index, text=text,
                embedding=embedding, extra_metadata=metadata,
            )
            s.add(chunk)

    @staticmethod
    def search(query: str, limit: int = 5) -> list[KnowledgeChunk]:
        """Simple text search (ILIKE). For embedding-based search, use vector similarity."""
        with session_scope() as s:
            chunks = (
                s.query(KnowledgeChunk)
                .filter(KnowledgeChunk.text.ilike(f"%{query}%"))
                .limit(limit).all()
            )
            for c in chunks:
                s.expunge(c)
            return chunks

    @staticmethod
    def list_sources() -> list[str]:
        with session_scope() as s:
            results = s.query(KnowledgeChunk.source).distinct().all()
            return [r[0] for r in results]

    @staticmethod
    def delete_source(source: str) -> int:
        with session_scope() as s:
            deleted = s.query(KnowledgeChunk).filter(
                KnowledgeChunk.source == source
            ).delete()
            return deleted


class AuditLogRepo:
    """Audit log data access."""

    @staticmethod
    def record(actor: str, action: str, target: str = None,
               details: dict = None, ip_address: str = None) -> None:
        with session_scope() as s:
            entry = AuditLog(
                actor=actor, action=action, target=target,
                details=details, ip_address=ip_address,
            )
            s.add(entry)

    @staticmethod
    def list_recent(limit: int = 100) -> list[AuditLog]:
        with session_scope() as s:
            entries = (
                s.query(AuditLog)
                .order_by(desc(AuditLog.created_at))
                .limit(limit).all()
            )
            for e in entries:
                s.expunge(e)
            return entries

    @staticmethod
    def list_by_action(action: str, limit: int = 50) -> list[AuditLog]:
        with session_scope() as s:
            entries = (
                s.query(AuditLog)
                .filter(AuditLog.action == action)
                .order_by(desc(AuditLog.created_at))
                .limit(limit).all()
            )
            for e in entries:
                s.expunge(e)
            return entries


class PluginStateRepo:
    """Plugin state data access."""

    @staticmethod
    def get(plugin_name: str) -> Optional[PluginState]:
        with session_scope() as s:
            ps = s.query(PluginState).filter(PluginState.plugin_name == plugin_name).first()
            if ps:
                s.expunge(ps)
            return ps

    @staticmethod
    def set_enabled(plugin_name: str, enabled: bool) -> None:
        with session_scope() as s:
            ps = s.query(PluginState).filter(PluginState.plugin_name == plugin_name).first()
            if ps:
                ps.enabled = enabled
                ps.updated_at = datetime.utcnow()
            else:
                ps = PluginState(plugin_name=plugin_name, enabled=enabled)
                s.add(ps)

    @staticmethod
    def update_state(plugin_name: str, state: dict) -> None:
        with session_scope() as s:
            ps = s.query(PluginState).filter(PluginState.plugin_name == plugin_name).first()
            if ps:
                ps.state = state
                ps.updated_at = datetime.utcnow()

    @staticmethod
    def update_config(plugin_name: str, config: dict) -> None:
        with session_scope() as s:
            ps = s.query(PluginState).filter(PluginState.plugin_name == plugin_name).first()
            if ps:
                ps.config = config
                ps.updated_at = datetime.utcnow()

    @staticmethod
    def list_all() -> list[PluginState]:
        with session_scope() as s:
            plugins = s.query(PluginState).all()
            for p in plugins:
                s.expunge(p)
            return plugins
