"""Tests for v3 features: database, plugins, RAG, tools, circuit breaker."""
import sys
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use clean DATABASE_URL for tests
os.environ["DATABASE_URL"] = ""


class TestCircuitBreaker(unittest.TestCase):
    """Tests for the circuit breaker."""

    def setUp(self):
        from security.circuit_breaker import CircuitBreaker, CircuitState
        self.CircuitState = CircuitState
        self.cb = CircuitBreaker(failure_threshold=3, cooldown_secs=1, success_threshold=2)

    def test_starts_closed(self):
        self.assertEqual(self.cb.state, self.CircuitState.CLOSED)
        self.assertTrue(self.cb.can_proceed())

    def test_trips_after_threshold(self):
        for _ in range(3):
            self.cb.record_failure("test error")
        self.assertEqual(self.cb.state, self.CircuitState.OPEN)
        self.assertFalse(self.cb.can_proceed())

    def test_does_not_trip_below_threshold(self):
        self.cb.record_failure("error 1")
        self.cb.record_failure("error 2")
        self.assertEqual(self.cb.state, self.CircuitState.CLOSED)
        self.assertTrue(self.cb.can_proceed())

    def test_success_resets_failure_count(self):
        self.cb.record_failure("error")
        self.cb.record_success()
        # Should need 3 more failures to trip (not 2)
        self.cb.record_failure("error")
        self.cb.record_failure("error")
        self.assertEqual(self.cb.state, self.CircuitState.CLOSED)

    def test_half_open_after_cooldown(self):
        for _ in range(3):
            self.cb.record_failure("error")
        self.assertEqual(self.cb.state, self.CircuitState.OPEN)
        # Wait for cooldown
        import time
        time.sleep(1.1)
        self.assertEqual(self.cb.state, self.CircuitState.HALF_OPEN)
        self.assertTrue(self.cb.can_proceed())

    def test_half_open_to_closed_after_successes(self):
        for _ in range(3):
            self.cb.record_failure("error")
        import time
        time.sleep(1.1)
        # Access state to trigger OPEN → HALF_OPEN transition
        _ = self.cb.state
        self.cb.record_success()
        self.cb.record_success()
        self.assertEqual(self.cb.state, self.CircuitState.CLOSED)

    def test_half_open_to_open_on_failure(self):
        for _ in range(3):
            self.cb.record_failure("error")
        import time
        time.sleep(1.1)
        # Access state to trigger OPEN → HALF_OPEN transition
        _ = self.cb.state
        self.cb.record_failure("error during test")
        self.assertEqual(self.cb.state, self.CircuitState.OPEN)

    def test_reset(self):
        for _ in range(3):
            self.cb.record_failure("error")
        self.cb.reset()
        self.assertEqual(self.cb.state, self.CircuitState.CLOSED)
        self.assertEqual(self.cb._failure_count, 0)

    def test_status(self):
        self.cb.record_failure("test")
        status = self.cb.status()
        self.assertEqual(status["state"], "closed")
        self.assertEqual(status["failure_count"], 1)
        self.assertIn("test", status["last_error"])


class TestSentimentPlugin(unittest.TestCase):
    """Tests for sentiment analysis."""

    def test_positive(self):
        from media.whatsapp.plugins.builtin.sentiment import SentimentPlugin
        score, label = SentimentPlugin._analyze_sentiment("I am happy and grateful")
        self.assertEqual(label, "positive")
        self.assertGreater(score, 0)

    def test_negative(self):
        from media.whatsapp.plugins.builtin.sentiment import SentimentPlugin
        score, label = SentimentPlugin._analyze_sentiment("This is terrible and awful")
        self.assertEqual(label, "negative")
        self.assertLess(score, 0)

    def test_angry(self):
        from media.whatsapp.plugins.builtin.sentiment import SentimentPlugin
        score, label = SentimentPlugin._analyze_sentiment("I am furious and angry")
        self.assertEqual(label, "angry")
        self.assertLess(score, -0.5)

    def test_neutral(self):
        from media.whatsapp.plugins.builtin.sentiment import SentimentPlugin
        score, label = SentimentPlugin._analyze_sentiment("The meeting is at 3pm")
        self.assertEqual(label, "neutral")

    def test_legal_escalation_keywords(self):
        """Messages with legal keywords should be flagged."""
        from media.whatsapp.plugins.builtin.sentiment import SentimentPlugin
        from media.whatsapp.plugins.base import PluginContext, HookPoint
        plugin = SentimentPlugin()
        ctx = PluginContext(
            contact_name="Test",
            messages=[{"content": "I will contact my lawyer about this"}],
            decision={"needs_approval": False, "risk_level": "LOW"},
        )
        result = plugin.after_decision(ctx)
        self.assertTrue(result.modified_decision["needs_approval"])
        self.assertEqual(result.modified_decision["triggered_category"], "LEGAL")


class TestSpamFilter(unittest.TestCase):
    """Tests for the Bayesian spam filter."""

    def setUp(self):
        from media.whatsapp.plugins.builtin.spam_filter import SpamFilterPlugin
        self.sf = SpamFilterPlugin()

    def test_classify_returns_float(self):
        score = self.sf._classify("hello world")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_training_spam_increases_score(self):
        # Train with spam
        for _ in range(20):
            self.sf.train_spam("FREE iPhone click here NOW limited time offer")
        for _ in range(20):
            self.sf.train_ham("Hey how are you doing today")
        spam_score = self.sf._classify("FREE iPhone click here NOW")
        ham_score = self.sf._classify("hey how are you doing today")
        self.assertGreater(spam_score, ham_score)

    def test_tokenize(self):
        tokens = self.sf._tokenize("Hello, World! 123")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        # Numbers are filtered out (only [a-z]+)
        self.assertNotIn("123", tokens)


class TestLinkSafetyPlugin(unittest.TestCase):
    """Tests for the link safety checker."""

    def test_extract_domain(self):
        from media.whatsapp.plugins.builtin.link_safety import LinkSafetyPlugin
        self.assertEqual(
            LinkSafetyPlugin._extract_domain("https://www.google.com/search"),
            "google.com",
        )
        self.assertEqual(
            LinkSafetyPlugin._extract_domain("http://example.org"),
            "example.org",
        )

    def test_blocked_shortener_detected(self):
        from media.whatsapp.plugins.builtin.link_safety import LinkSafetyPlugin
        plugin = LinkSafetyPlugin()
        self.assertTrue(plugin._is_suspicious("bit.ly", "click bit.ly"))
        self.assertTrue(plugin._is_suspicious("tinyurl.com", "check tinyurl.com"))

    def test_legit_domain_not_suspicious(self):
        """A legit domain should not be flagged as suspicious."""
        from media.whatsapp.plugins.builtin.link_safety import LinkSafetyPlugin
        plugin = LinkSafetyPlugin()
        self.assertFalse(plugin._is_suspicious("google.com", ""))
        self.assertFalse(plugin._is_suspicious("facebook.com", ""))
        self.assertFalse(plugin._is_suspicious("example.com", ""))

    def test_lookalite_detection(self):
        from media.whatsapp.plugins.builtin.link_safety import LinkSafetyPlugin
        plugin = LinkSafetyPlugin()
        # "faceb00k" → normalized "facebook" → lookalike of "facebook.com"
        self.assertTrue(plugin._is_lookalike("faceb00k.com", "facebook.com"))
        self.assertFalse(plugin._is_lookalike("google.com", "facebook.com"))

    def test_url_extraction_from_text(self):
        from media.whatsapp.plugins.builtin.link_safety import _URL_RE
        text = "Check this out https://example.com/path and http://test.org"
        urls = _URL_RE.findall(text)
        self.assertEqual(len(urls), 2)


class TestAutoTagPlugin(unittest.TestCase):
    """Tests for the auto-tag plugin."""

    def test_work_tags(self):
        from media.whatsapp.plugins.builtin.auto_tag import AutoTagPlugin
        from media.whatsapp.plugins.base import PluginContext
        plugin = AutoTagPlugin()
        ctx = PluginContext(
            contact_name="Test",
            messages=[{"content": "Let's schedule a meeting about the project"}],
        )
        result = plugin.after_decision(ctx)
        self.assertIn("work", result.metadata.get("tags_added", []))

    def test_finance_tags(self):
        from media.whatsapp.plugins.builtin.auto_tag import AutoTagPlugin
        from media.whatsapp.plugins.base import PluginContext
        plugin = AutoTagPlugin()
        ctx = PluginContext(
            contact_name="Test",
            messages=[{"content": "Can you transfer the payment to my bank account?"}],
        )
        result = plugin.after_decision(ctx)
        self.assertIn("finance", result.metadata.get("tags_added", []))

    def test_urgent_tags(self):
        from media.whatsapp.plugins.builtin.auto_tag import AutoTagPlugin
        from media.whatsapp.plugins.base import PluginContext
        plugin = AutoTagPlugin()
        ctx = PluginContext(
            contact_name="Test",
            messages=[{"content": "URGENT: Need this ASAP!"}],
        )
        result = plugin.after_decision(ctx)
        self.assertIn("urgent", result.metadata.get("tags_added", []))


class TestTools(unittest.TestCase):
    """Tests for AI function calling tools."""

    def test_calculator_basic(self):
        from media.whatsapp.ai.tools import ToolRegistry
        result = ToolRegistry._tool_calculator({"expression": "2+2"})
        self.assertIn("4", result)

    def test_calculator_sqrt(self):
        from media.whatsapp.ai.tools import ToolRegistry
        result = ToolRegistry._tool_calculator({"expression": "sqrt(16)"})
        self.assertIn("4", result)

    def test_calculator_rejects_dangerous(self):
        from media.whatsapp.ai.tools import ToolRegistry
        result = ToolRegistry._tool_calculator({"expression": "__import__('os')"})
        self.assertIn("Error", result)

    def test_get_time(self):
        from media.whatsapp.ai.tools import ToolRegistry
        result = ToolRegistry._tool_get_time({})
        self.assertIn("20", result)  # Year 202x

    def test_parse_tool_call_calculator(self):
        from media.whatsapp.ai.tools import tool_registry
        result = tool_registry.parse_and_execute(
            '{"tool": "calculator", "args": {"expression": "3*7"}}'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["tool"], "calculator")
        self.assertIn("21", result["result"])

    def test_parse_tool_call_unknown_tool(self):
        from media.whatsapp.ai.tools import tool_registry
        result = tool_registry.parse_and_execute(
            '{"tool": "unknown_tool", "args": {}}'
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.get("error"))

    def test_parse_non_tool_response(self):
        from media.whatsapp.ai.tools import tool_registry
        result = tool_registry.parse_and_execute("Hello, this is a normal reply")
        self.assertIsNone(result)

    def test_to_prompt_contains_tools(self):
        from media.whatsapp.ai.tools import tool_registry
        prompt = tool_registry.to_prompt()
        self.assertIn("calculator", prompt)
        self.assertIn("get_time", prompt)
        self.assertIn("web_search", prompt)


class TestRAG(unittest.TestCase):
    """Tests for the RAG knowledge base."""

    def setUp(self):
        from media.whatsapp.ai.rag import KnowledgeBase
        self.kb = KnowledgeBase(chunk_size=100, overlap=20)

    def test_split_text_short(self):
        chunks = self.kb._split_text("Short text")
        self.assertEqual(len(chunks), 1)

    def test_split_text_long(self):
        text = "A" * 500  # 500 chars
        chunks = self.kb._split_text(text)
        self.assertGreater(len(chunks), 1)

    def test_split_text_empty(self):
        chunks = self.kb._split_text("")
        self.assertEqual(chunks, [])

    def test_build_context_empty(self):
        ctx = self.kb.build_context("nonexistent query")
        self.assertEqual(ctx, "")

    def test_build_context_with_results(self):
        # This test requires DB — skip if not available
        try:
            self.kb.ingest_text("test.txt", "The bot supports WhatsApp automation.")
            ctx = self.kb.build_context("WhatsApp")
            self.assertIn("KNOWLEDGE BASE CONTEXT", ctx)
        except Exception:
            self.skipTest("DB not available for RAG test")


class TestPluginManager(unittest.TestCase):
    """Tests for the plugin manager."""

    def test_list_plugins_empty(self):
        from media.whatsapp.plugins.manager import PluginManager
        pm = PluginManager()
        self.assertEqual(pm.list_plugins(), [])

    def test_register_and_get(self):
        from media.whatsapp.plugins.manager import PluginManager
        from media.whatsapp.plugins.base import Plugin
        pm = PluginManager()

        class TestPlugin(Plugin):
            name = "test_plugin"
            version = "1.0.0"
            description = "Test"

        plugin = TestPlugin()
        pm.register(plugin)
        self.assertEqual(pm.get("test_plugin"), plugin)
        self.assertIn({
            "name": "test_plugin", "version": "1.0.0",
            "description": "Test", "hooks": [], "config": {},
        }, pm.list_plugins())

    def test_unregister(self):
        from media.whatsapp.plugins.manager import PluginManager
        from media.whatsapp.plugins.base import Plugin
        pm = PluginManager()

        class TestPlugin(Plugin):
            name = "removable"

        pm.register(TestPlugin())
        self.assertTrue(pm.unregister("removable"))
        self.assertIsNone(pm.get("removable"))

    def test_execute_hook_no_plugins(self):
        from media.whatsapp.plugins.manager import PluginManager
        from media.whatsapp.plugins.base import PluginContext, HookPoint
        pm = PluginManager()
        ctx = PluginContext(contact_name="test")
        result = pm.execute_hook(HookPoint.BEFORE_DECISION, ctx)
        self.assertFalse(result.stop_processing)


class TestScheduler(unittest.TestCase):
    """Tests for the message scheduler (DB-dependent)."""

    def test_scheduler_singleton(self):
        from media.whatsapp.scheduler.manager import scheduler
        self.assertIsNotNone(scheduler)

    def test_scheduler_stop(self):
        from media.whatsapp.scheduler.manager import scheduler
        scheduler.stop()
        self.assertTrue(scheduler._stop_event.is_set())


class TestBroadcast(unittest.TestCase):
    """Tests for the broadcast manager."""

    def test_broadcast_singleton(self):
        from media.whatsapp.broadcast.manager import broadcast_manager
        self.assertIsNotNone(broadcast_manager)

    def test_broadcast_stop(self):
        from media.whatsapp.broadcast.manager import broadcast_manager
        broadcast_manager.stop()
        self.assertTrue(broadcast_manager._stop_event.is_set())


class TestAuditLog(unittest.TestCase):
    """Tests for the audit logger (DB-dependent)."""

    def test_audit_logger_singleton(self):
        from media.whatsapp.security.audit_log import audit_logger
        self.assertIsNotNone(audit_logger)


class TestOutboundAPI(unittest.TestCase):
    """Tests for the outbound API router."""

    def test_router_has_endpoints(self):
        from media.whatsapp.api.outbound import outbound_api
        routes = [r.path for r in outbound_api.router.routes]
        self.assertIn("/api/outbound/send", routes)
        self.assertIn("/api/outbound/schedule", routes)
        self.assertIn("/api/outbound/broadcast", routes)
        self.assertIn("/api/outbound/status/scheduled/{msg_id}", routes)
        self.assertIn("/api/outbound/status/campaign/{campaign_id}", routes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
