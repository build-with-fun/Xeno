"""Typed data structures used across the project.

Replaces the original code's pervasive use of untyped `dict`s, which made it
impossible to know what fields a message/persona/decision actually had without
grepping the whole codebase.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class MessageKind(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    PDF = "pdf"
    DOCX = "docx"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class RiskLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DecisionCategory(str, enum.Enum):
    FINANCIAL = "FINANCIAL"
    SCHEDULING = "SCHEDULING"
    SECURITY = "SECURITY"
    LEGAL = "LEGAL"
    RETRACTION = "RETRACTION"
    CASUAL = "CASUAL"
    VOICE = "VOICE"
    MEDIA = "MEDIA"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class Message:
    """A raw message as fetched from WhatsApp via WPP.js."""
    id: str
    kind: MessageKind = MessageKind.TEXT
    body: str = ""
    caption: str = ""
    filename: str = ""
    mimetype: str = ""
    from_me: bool = False
    timestamp: float = 0.0
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_wpp(cls, m: dict) -> "Message":
        """Build a Message from a WPP.js message dict."""
        kind_str = str(m.get("type", "text")).lower()
        try:
            kind = MessageKind(kind_str) if kind_str in MessageKind.__members__.values() else MessageKind.TEXT
        except ValueError:
            kind = MessageKind.TEXT
        # Re-classify based on mimetype/filename for documents
        mime = (m.get("mimetype") or "").lower()
        fname = (m.get("filename") or "").lower()
        if kind == MessageKind.TEXT:
            if mime.startswith("audio/") or kind_str in ("ptt", "audio"):
                kind = MessageKind.VOICE
            elif mime.startswith("image/"):
                kind = MessageKind.IMAGE
            elif mime.startswith("video/"):
                kind = MessageKind.VIDEO
            elif "pdf" in mime or fname.endswith(".pdf"):
                kind = MessageKind.PDF
            elif fname.endswith((".docx", ".doc")) or "word" in mime:
                kind = MessageKind.DOCX
            elif kind_str == "sticker":
                kind = MessageKind.STICKER
        return cls(
            id=m.get("id", "") or "",
            kind=kind,
            body=m.get("body", "") or "",
            caption=m.get("caption", "") or "",
            filename=m.get("filename", "") or "",
            mimetype=mime,
            from_me=bool(m.get("fromMe", False)),
            timestamp=float(m.get("t", 0.0) or 0.0),
            raw=m,
        )


@dataclass
class ProcessedMessage:
    """A message after media processing (transcription / OCR / extraction)."""
    label: str
    content: str
    kind: MessageKind = MessageKind.TEXT
    caption: str = ""
    image_bytes: Optional[bytes] = None
    mimetype: str = "image/jpeg"
    raw_msg_id: str = ""


@dataclass
class Decision:
    """Output of the safety decision engine."""
    needs_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    is_retraction: bool = False
    reason: str = "No reason provided."
    retraction_reply: str = ""
    confidence: float = 0.5
    triggered_category: DecisionCategory = DecisionCategory.CASUAL
    provider: str = "unknown"

    @classmethod
    def from_dict(cls, d: dict, provider: str = "unknown") -> "Decision":
        """Build a Decision from a parsed AI response dict."""
        try:
            risk = RiskLevel(d.get("risk_level", "LOW"))
        except ValueError:
            risk = RiskLevel.LOW
        try:
            cat = DecisionCategory(d.get("triggered_category", "CASUAL"))
        except ValueError:
            cat = DecisionCategory.CASUAL
        return cls(
            needs_approval=bool(d.get("needs_approval", False)),
            risk_level=risk,
            is_retraction=bool(d.get("is_retraction", False)),
            reason=str(d.get("reason", "No reason provided."))[:500],
            retraction_reply=str(d.get("retraction_reply", ""))[:1000],
            confidence=float(d.get("confidence", 0.5)),
            triggered_category=cat,
            provider=provider,
        )

    def to_dict(self) -> dict:
        return {
            "needs_approval": self.needs_approval,
            "risk_level": self.risk_level.value,
            "is_retraction": self.is_retraction,
            "reason": self.reason,
            "retraction_reply": self.retraction_reply,
            "confidence": self.confidence,
            "triggered_category": self.triggered_category.value,
            "provider": self.provider,
        }


@dataclass
class Persona:
    """A persona definition for reply generation."""
    name: str = "Alex"
    age: int = 25
    language: str = "English"
    style: str = "casual"
    system_prompt_extra: str = (
        "You are a real person texting on WhatsApp. "
        "Match the energy of whoever is texting you."
    )
    fallback_reply: str = "Hey! Talk later :)"

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        return cls(
            name=str(d.get("name", "Alex")),
            age=int(d.get("age", 25)),
            language=str(d.get("language", "English")),
            style=str(d.get("style", "casual")),
            system_prompt_extra=str(d.get("system_prompt_extra", "")),
            fallback_reply=str(d.get("fallback_reply", "Hey! Talk later :)")),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name, "age": self.age, "language": self.language,
            "style": self.style, "system_prompt_extra": self.system_prompt_extra,
            "fallback_reply": self.fallback_reply,
        }


@dataclass
class ConversationEntry:
    """A single entry in a contact's conversation history."""
    role: str  # "user" | "assistant" | "system"
    content: str
    kind: str = "text"  # text|voice|image|pdf|docx|summary
    label: str = "Text"
    display: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role, "type": self.kind, "content": self.content,
            "display": self.display, "label": self.label, "ts": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationEntry":
        return cls(
            role=str(d.get("role", "user")),
            content=str(d.get("content", "")),
            kind=str(d.get("type", "text")),
            label=str(d.get("label", "Text")),
            display=str(d.get("display", "")),
            timestamp=str(d.get("ts", "")),
        )


@dataclass
class ApprovalItem:
    """An item in the approval queue."""
    msg_id: int
    contact: str
    timestamp: str
    messages: list  # list of dict (serialized ProcessedMessage)
    decision: dict
    status: str = "pending"  # pending|approved|rejected|processing|sent|failed
    approved_at: Optional[str] = None
    custom_context: str = ""
    custom_reply: str = ""
    error: str = ""
    attempts: int = 0
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id, "contact": self.contact,
            "timestamp": self.timestamp, "messages": self.messages,
            "decision": self.decision, "status": self.status,
            "approved_at": self.approved_at,
            "custom_context": self.custom_context,
            "custom_reply": self.custom_reply,
            "error": self.error, "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, d: dict, file_path: str = "") -> "ApprovalItem":
        return cls(
            msg_id=int(d.get("msg_id", 0)),
            contact=str(d.get("contact", "")),
            timestamp=str(d.get("timestamp", "")),
            messages=list(d.get("messages", [])),
            decision=dict(d.get("decision", {})),
            status=str(d.get("status", "pending")),
            approved_at=d.get("approved_at"),
            custom_context=str(d.get("custom_context", "")),
            custom_reply=str(d.get("custom_reply", "")),
            error=str(d.get("error", "")),
            attempts=int(d.get("attempts", 0)),
            file_path=file_path,
        )


@dataclass
class RetryItem:
    """An item in the retry queue."""
    contact: str
    reply: str
    attempt: int = 0
    next_retry_at: str = ""
    original_ts: str = ""
    file_path: str = ""
    last_error: str = ""
