"""SQLAlchemy ORM models for all persistent data.

Replaces v2's JSON-file storage with proper relational tables.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer,
    String, Text, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ── Enums ───────────────────────────────────────────────────────────────────

class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageKind(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    PDF = "pdf"
    DOCX = "docx"
    STICKER = "sticker"
    SUMMARY = "summary"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# ── Models ──────────────────────────────────────────────────────────────────

class Contact(Base):
    """A WhatsApp contact."""
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # ["friend", "work"]
    notes: Mapped[Optional[str]] = mapped_column(Text)
    persona_override: Mapped[Optional[dict]] = mapped_column(JSON)  # per-contact persona
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[Optional[str]] = mapped_column(String(10))  # detected language
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)  # running avg
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_replies: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship(back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_contact_name_phone", "name", "phone"),)


class Message(Base):
    """A message in a conversation."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind), default=MessageKind.TEXT)
    content: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(50), default="Text")
    whatsapp_msg_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    sentiment: Mapped[Optional[Sentiment]] = mapped_column(Enum(Sentiment))
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    spam_score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_provider: Mapped[Optional[str]] = mapped_column(String(50))  # "gemini", "groq", etc.
    response_time_secs: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    contact: Mapped["Contact"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_msg_contact_time", "contact_id", "created_at"),
        Index("idx_msg_created", "created_at"),
    )


class Approval(Base):
    """An item in the approval queue."""
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    msg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    contact_name: Mapped[str] = mapped_column(String(255), index=True)
    messages: Mapped[list] = mapped_column(JSON)  # serialized processed messages
    decision: Mapped[dict] = mapped_column(JSON)  # AI decision
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True
    )
    custom_context: Mapped[Optional[str]] = mapped_column(Text)
    custom_reply: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RetryItem(Base):
    """An item in the retry queue."""
    __tablename__ = "retry_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_name: Mapped[str] = mapped_column(String(255), index=True)
    reply: Mapped[str] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalyticsEvent(Base):
    """A single analytics event (for time-series analysis)."""
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)  # "received", "sent", etc.
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    extra: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("idx_analytics_type_time", "event_type", "created_at"),)


class ScheduledMessage(Base):
    """A message scheduled to be sent in the future."""
    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_name: Mapped[str] = mapped_column(String(255), index=True)
    text: Mapped[str] = mapped_column(Text)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|cancelled|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)
    recurrence: Mapped[Optional[str]] = mapped_column(String(50))  # daily|weekly|monthly|None


class BroadcastCampaign(Base):
    """A broadcast campaign (mass messaging)."""
    __tablename__ = "broadcast_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    template: Mapped[str] = mapped_column(Text)  # "Hi {name}, {message}"
    variables: Mapped[Optional[dict]] = mapped_column(JSON)  # per-recipient vars
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)

    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class BroadcastRecipient(Base):
    """A recipient in a broadcast campaign."""
    __tablename__ = "broadcast_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("broadcast_campaigns.id"), index=True)
    contact_name: Mapped[str] = mapped_column(String(255), index=True)
    personalized_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|failed
    error: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    campaign: Mapped["BroadcastCampaign"] = relationship(back_populates="recipients")


class KnowledgeChunk(Base):
    """A chunk of text in the RAG knowledge base."""
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(255), index=True)  # filename or URL
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[bytes]] = mapped_column(Text)  # base64-encoded float array
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)  # column name stays "metadata"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_knowledge_source", "source"),)


class AuditLog(Base):
    """Audit trail for admin actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))  # who did it (API token, CLI user)
    action: Mapped[str] = mapped_column(String(100), index=True)  # "approve", "reject", "stop", etc.
    target: Mapped[Optional[str]] = mapped_column(String(255))  # msg_id, contact, etc.
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PluginState(Base):
    """Persistent state for plugins."""
    __tablename__ = "plugin_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plugin_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON)
    state: Mapped[Optional[dict]] = mapped_column(JSON)  # arbitrary plugin state
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
