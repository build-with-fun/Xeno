"""Tests for ai/prompts.py and ai/base.py (JSON parsing, registry)."""
import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media.whatsapp.ai.prompts import (
    DECISION_SYSTEM_PROMPT,
    build_reply_system_prompt,
    build_summary_prompt,
)
from media.whatsapp.ai.base import AIRegistry, ProviderCapability
from media.whatsapp.ai.gemini import GeminiProvider
from media.whatsapp.ai.groq import GroqProvider
from media.whatsapp.core.types import Persona


class TestDecisionPrompt(unittest.TestCase):
    def test_contains_required_sections(self):
        self.assertIn("ALWAYS NEEDS APPROVAL", DECISION_SYSTEM_PROMPT)
        self.assertIn("FINANCIAL", DECISION_SYSTEM_PROMPT)
        self.assertIn("SCHEDULING", DECISION_SYSTEM_PROMPT)
        self.assertIn("SECURITY", DECISION_SYSTEM_PROMPT)
        self.assertIn("LEGAL", DECISION_SYSTEM_PROMPT)
        self.assertIn("ALWAYS AUTO-REPLY", DECISION_SYSTEM_PROMPT)
        self.assertIn("VOICE NOTES", DECISION_SYSTEM_PROMPT)
        self.assertIn("RETRACTION DETECTION", DECISION_SYSTEM_PROMPT)

    def test_contains_json_schema(self):
        self.assertIn("needs_approval", DECISION_SYSTEM_PROMPT)
        self.assertIn("risk_level", DECISION_SYSTEM_PROMPT)
        self.assertIn("is_retraction", DECISION_SYSTEM_PROMPT)
        self.assertIn("confidence", DECISION_SYSTEM_PROMPT)
        self.assertIn("triggered_category", DECISION_SYSTEM_PROMPT)

    def test_contains_hard_rules(self):
        self.assertIn("HARD RULES", DECISION_SYSTEM_PROMPT)
        self.assertIn("Output ONLY raw JSON", DECISION_SYSTEM_PROMPT)


class TestBuildReplySystemPrompt(unittest.TestCase):
    def test_includes_persona_name(self):
        persona = Persona(name="Sara")
        prompt = build_reply_system_prompt(persona, "history here", "")
        self.assertIn("Sara", prompt)

    def test_includes_history(self):
        persona = Persona()
        prompt = build_reply_system_prompt(persona, "REMEMBER THIS", "")
        self.assertIn("REMEMBER THIS", prompt)

    def test_includes_custom_context(self):
        persona = Persona()
        prompt = build_reply_system_prompt(persona, "", "BE EXTRA FORMAL")
        self.assertIn("BE EXTRA FORMAL", prompt)
        self.assertIn("CUSTOM INSTRUCTIONS", prompt)

    def test_no_custom_context_section_when_empty(self):
        persona = Persona()
        prompt = build_reply_system_prompt(persona, "", "")
        self.assertNotIn("CUSTOM INSTRUCTIONS", prompt)

    def test_contains_language_rules(self):
        persona = Persona()
        prompt = build_reply_system_prompt(persona, "", "")
        self.assertIn("LANGUAGE RULES", prompt)
        self.assertIn("Never reveal you are an AI", prompt)

    def test_contains_tone_matching(self):
        persona = Persona()
        prompt = build_reply_system_prompt(persona, "", "")
        self.assertIn("TONE MATCHING", prompt)


class TestBuildSummaryPrompt(unittest.TestCase):
    def test_includes_old_summary(self):
        prompt = build_summary_prompt("OLD SUMMARY TEXT", "new messages")
        self.assertIn("OLD SUMMARY TEXT", prompt)

    def test_includes_new_messages(self):
        prompt = build_summary_prompt("old", "NEW MESSAGES HERE")
        self.assertIn("NEW MESSAGES HERE", prompt)

    def test_contains_instructions(self):
        prompt = build_summary_prompt("old", "new")
        self.assertIn("Summarize", prompt)
        self.assertIn("Max 250 words", prompt)


class TestAIRegistry(unittest.TestCase):
    """Tests for the cooldown registry."""

    def setUp(self):
        self.reg = AIRegistry()

    def test_key_hash_consistent(self):
        """Same key produces same hash."""
        h1 = self.reg._hash_key("my-api-key-123")
        h2 = self.reg._hash_key("my-api-key-123")
        self.assertEqual(h1, h2)

    def test_key_hash_different_for_different_keys(self):
        h1 = self.reg._hash_key("key-one")
        h2 = self.reg._hash_key("key-two")
        self.assertNotEqual(h1, h2)

    def test_key_hash_truncated(self):
        """Hash is truncated to 16 chars (privacy + fixed length)."""
        h = self.reg._hash_key("a" * 100)
        self.assertEqual(len(h), 16)

    def test_no_cooldown_by_default(self):
        self.assertFalse(self.reg.is_on_cooldown("any-key"))
        self.assertEqual(self.reg.cooldown_remaining("any-key"), 0.0)

    def test_set_and_check_cooldown(self):
        self.reg.set_cooldown("limited-key", seconds=60)
        self.assertTrue(self.reg.is_on_cooldown("limited-key"))
        remaining = self.reg.cooldown_remaining("limited-key")
        self.assertGreater(remaining, 58)
        self.assertLessEqual(remaining, 60)

    def test_cooldown_expires(self):
        self.reg.set_cooldown("short-key", seconds=0)
        # 0-second cooldown should be expired immediately
        self.assertFalse(self.reg.is_on_cooldown("short-key"))

    def test_classify_error_429(self):
        self.assertTrue(self.reg.classify_error(Exception("429 Too Many Requests")))

    def test_classify_error_quota(self):
        self.assertTrue(self.reg.classify_error(Exception("quota exceeded")))

    def test_classify_error_rate_limit(self):
        self.assertTrue(self.reg.classify_error(Exception("rate limit exceeded")))

    def test_classify_error_resource_exhausted(self):
        self.assertTrue(self.reg.classify_error(Exception("ResourceExhausted 429")))

    def test_classify_error_normal(self):
        self.assertFalse(self.reg.classify_error(Exception("internal server error")))
        self.assertFalse(self.reg.classify_error(Exception("invalid api key")))


class TestGeminiJSONParsing(unittest.TestCase):
    """Tests for GeminiProvider._parse_json — extraction from messy LLM output."""

    def test_clean_json(self):
        raw = '{"needs_approval": true, "risk_level": "HIGH"}'
        result = GeminiProvider._parse_json(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result["needs_approval"])

    def test_json_in_code_block(self):
        raw = '```json\n{"needs_approval": false, "risk_level": "LOW"}\n```'
        result = GeminiProvider._parse_json(raw)
        self.assertIsNotNone(result)
        self.assertFalse(result["needs_approval"])

    def test_json_with_surrounding_text(self):
        raw = 'Here is my decision:\n{"needs_approval": true, "risk_level": "CRITICAL"}\nHope this helps.'
        result = GeminiProvider._parse_json(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result["needs_approval"])
        self.assertEqual(result["risk_level"], "CRITICAL")

    def test_missing_needs_approval_returns_none(self):
        raw = '{"risk_level": "HIGH"}'  # no needs_approval key
        result = GeminiProvider._parse_json(raw)
        self.assertIsNone(result)

    def test_empty_string(self):
        self.assertIsNone(GeminiProvider._parse_json(""))

    def test_none_input(self):
        self.assertIsNone(GeminiProvider._parse_json(None))

    def test_defaults_filled(self):
        raw = '{"needs_approval": true}'
        result = GeminiProvider._parse_json(raw)
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(result["is_retraction"], False)
        self.assertEqual(result["confidence"], 0.5)
        self.assertEqual(result["triggered_category"], "CASUAL")

    def test_invalid_json(self):
        raw = 'this is not json at all'
        result = GeminiProvider._parse_json(raw)
        self.assertIsNone(result)

    def test_nested_json_extracted(self):
        """Should find the JSON object even if nested in other text."""
        raw = 'Analysis: {"needs_approval": false, "reason": "casual chat", "confidence": 0.9}'
        result = GeminiProvider._parse_json(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "casual chat")


class TestGroqJSONParsing(unittest.TestCase):
    """Same parsing logic, separate tests for clarity."""

    def test_clean_json(self):
        raw = '{"needs_approval": true, "risk_level": "HIGH"}'
        result = GroqProvider._parse_json(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result["needs_approval"])

    def test_code_block(self):
        raw = '```json\n{"needs_approval": false}\n```'
        result = GroqProvider._parse_json(raw)
        self.assertIsNotNone(result)


class TestProviderCapability(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(ProviderCapability.TEXT.value, "text")
        self.assertEqual(ProviderCapability.VISION.value, "vision")
        self.assertEqual(ProviderCapability.JSON.value, "json")

    def test_is_string_enum(self):
        self.assertIsInstance(ProviderCapability.TEXT, str)


class TestProviderConstruction(unittest.TestCase):
    def test_gemini_requires_key(self):
        with self.assertRaises(ValueError):
            GeminiProvider("")

    def test_groq_requires_key(self):
        with self.assertRaises(ValueError):
            GroqProvider("")

    def test_gemini_available_with_key(self):
        p = GeminiProvider("fake-key")
        self.assertTrue(p.is_available())

    def test_gemini_not_on_cooldown_initially(self):
        p = GeminiProvider("fake-key")
        self.assertFalse(p.is_on_cooldown())
        self.assertEqual(p.cooldown_remaining(), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
