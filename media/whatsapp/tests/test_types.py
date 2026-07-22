"""Tests for core.types — dataclass construction, serialization, enum handling."""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media.whatsapp.core.types import (
    Message, ProcessedMessage, Decision, Persona,
    ConversationEntry, ApprovalItem, RetryItem,
    MessageKind, RiskLevel, DecisionCategory,
)


class TestMessageKind(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(MessageKind.TEXT.value, "text")
        self.assertEqual(MessageKind.VOICE.value, "voice")
        self.assertEqual(MessageKind.IMAGE.value, "image")
        self.assertEqual(MessageKind.PDF.value, "pdf")

    def test_is_string_enum(self):
        """MessageKind is str+enum so JSON serialization works natively."""
        self.assertIsInstance(MessageKind.TEXT, str)
        self.assertEqual(MessageKind.TEXT, "text")


class TestMessageFromWPP(unittest.TestCase):
    """Tests for Message.from_wpp — converts WPP.js dicts to typed Message."""

    def test_simple_text(self):
        m = Message.from_wpp({
            "id": "msg_1",
            "type": "chat",
            "body": "Hello!",
            "fromMe": False,
        })
        self.assertEqual(m.id, "msg_1")
        self.assertEqual(m.body, "Hello!")
        self.assertFalse(m.from_me)
        self.assertEqual(m.kind, MessageKind.TEXT)

    def test_voice_message(self):
        m = Message.from_wpp({
            "id": "msg_2",
            "type": "ptt",
            "mimetype": "audio/ogg",
        })
        self.assertEqual(m.kind, MessageKind.VOICE)

    def test_image_message(self):
        m = Message.from_wpp({
            "id": "msg_3",
            "type": "image",
            "mimetype": "image/jpeg",
            "caption": "Look at this",
        })
        self.assertEqual(m.kind, MessageKind.IMAGE)
        self.assertEqual(m.caption, "Look at this")

    def test_pdf_document(self):
        m = Message.from_wpp({
            "id": "msg_4",
            "type": "document",
            "mimetype": "application/pdf",
            "filename": "report.pdf",
        })
        self.assertEqual(m.kind, MessageKind.PDF)
        self.assertEqual(m.filename, "report.pdf")

    def test_docx_document(self):
        m = Message.from_wpp({
            "id": "msg_5",
            "type": "document",
            "filename": "notes.docx",
        })
        self.assertEqual(m.kind, MessageKind.DOCX)

    def test_sticker(self):
        m = Message.from_wpp({"id": "s1", "type": "sticker"})
        self.assertEqual(m.kind, MessageKind.STICKER)

    def test_missing_id(self):
        """A message with no ID should still construct (empty string)."""
        m = Message.from_wpp({"type": "chat", "body": "hi"})
        self.assertEqual(m.id, "")

    def test_unknown_type_defaults_to_text(self):
        m = Message.from_wpp({"id": "x", "type": "unknown_future_type"})
        self.assertEqual(m.kind, MessageKind.TEXT)


class TestDecision(unittest.TestCase):
    def test_from_dict_complete(self):
        d = Decision.from_dict({
            "needs_approval": True,
            "risk_level": "HIGH",
            "is_retraction": False,
            "reason": "Financial request detected",
            "retraction_reply": "",
            "confidence": 0.85,
            "triggered_category": "FINANCIAL",
        }, provider="gemini")
        self.assertTrue(d.needs_approval)
        self.assertEqual(d.risk_level, RiskLevel.HIGH)
        self.assertEqual(d.triggered_category, DecisionCategory.FINANCIAL)
        self.assertEqual(d.provider, "gemini")
        self.assertAlmostEqual(d.confidence, 0.85)

    def test_from_dict_defaults(self):
        """Missing fields get safe defaults."""
        d = Decision.from_dict({"needs_approval": False})
        self.assertFalse(d.needs_approval)
        self.assertEqual(d.risk_level, RiskLevel.LOW)
        self.assertFalse(d.is_retraction)
        self.assertEqual(d.confidence, 0.5)
        self.assertEqual(d.triggered_category, DecisionCategory.CASUAL)

    def test_from_dict_invalid_enum_falls_back(self):
        d = Decision.from_dict({
            "needs_approval": True,
            "risk_level": "EXTREME",  # invalid
            "triggered_category": "NUKE",  # invalid
        })
        self.assertTrue(d.needs_approval)
        self.assertEqual(d.risk_level, RiskLevel.LOW)
        self.assertEqual(d.triggered_category, DecisionCategory.CASUAL)

    def test_to_dict_roundtrip(self):
        original = Decision(
            needs_approval=True,
            risk_level=RiskLevel.CRITICAL,
            is_retraction=False,
            reason="test",
            confidence=0.9,
            triggered_category=DecisionCategory.SECURITY,
            provider="groq",
        )
        d = original.to_dict()
        restored = Decision.from_dict(d, provider="groq")
        self.assertEqual(restored.needs_approval, original.needs_approval)
        self.assertEqual(restored.risk_level, original.risk_level)
        self.assertEqual(restored.triggered_category, original.triggered_category)
        self.assertAlmostEqual(restored.confidence, original.confidence)

    def test_reason_truncated(self):
        """Very long reasons are truncated to prevent log bloat."""
        long_reason = "x" * 1000
        d = Decision.from_dict({"needs_approval": True, "reason": long_reason})
        self.assertLessEqual(len(d.reason), 500)


class TestPersona(unittest.TestCase):
    def test_defaults(self):
        p = Persona()
        self.assertEqual(p.name, "Alex")
        self.assertEqual(p.age, 25)
        self.assertIn("real person", p.system_prompt_extra)

    def test_from_dict(self):
        p = Persona.from_dict({
            "name": "Sara",
            "age": 30,
            "language": "Urdu",
            "style": "formal",
        })
        self.assertEqual(p.name, "Sara")
        self.assertEqual(p.age, 30)
        self.assertEqual(p.language, "Urdu")

    def test_from_dict_partial(self):
        """Missing fields use defaults."""
        p = Persona.from_dict({"name": "Bob"})
        self.assertEqual(p.name, "Bob")
        self.assertEqual(p.age, 25)  # default

    def test_to_dict_roundtrip(self):
        original = Persona(name="Test", age=40, language="French")
        d = original.to_dict()
        restored = Persona.from_dict(d)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.age, original.age)
        self.assertEqual(restored.language, original.language)


class TestConversationEntry(unittest.TestCase):
    def test_to_dict(self):
        e = ConversationEntry(
            role="user", content="Hello", kind="text",
            label="Text", display='Them [Text]: "Hello"',
            timestamp="2025-01-01 10:00:00",
        )
        d = e.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "Hello")
        self.assertEqual(d["type"], "text")
        self.assertEqual(d["ts"], "2025-01-01 10:00:00")

    def test_from_dict(self):
        d = {
            "role": "assistant", "content": "Hi there", "type": "text",
            "display": "You [Text]: Hi there", "label": "Text",
            "ts": "2025-01-01 10:01:00",
        }
        e = ConversationEntry.from_dict(d)
        self.assertEqual(e.role, "assistant")
        self.assertEqual(e.content, "Hi there")
        self.assertEqual(e.timestamp, "2025-01-01 10:01:00")


class TestApprovalItem(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        original = ApprovalItem(
            msg_id=12345,
            contact="Alice",
            timestamp="2025-01-01T10:00:00",
            messages=[{"label": "Text", "content": "Send money"}],
            decision={"needs_approval": True, "risk_level": "HIGH"},
            status="pending",
        )
        d = original.to_dict()
        restored = ApprovalItem.from_dict(d, file_path="/tmp/test.json")
        self.assertEqual(restored.msg_id, original.msg_id)
        self.assertEqual(restored.contact, original.contact)
        self.assertEqual(restored.status, original.status)
        self.assertEqual(len(restored.messages), 1)


class TestRetryItem(unittest.TestCase):
    def test_construction(self):
        r = RetryItem(
            contact="Bob", reply="Hello back", attempt=2,
            next_retry_at="2025-01-01T10:05:00",
        )
        self.assertEqual(r.contact, "Bob")
        self.assertEqual(r.attempt, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
