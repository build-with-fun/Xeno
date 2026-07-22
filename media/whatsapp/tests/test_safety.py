"""Tests for safety/ — keyword alerts and rate limiter."""
import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp directory for test data
import tempfile
_TMP = tempfile.mkdtemp(prefix="wabot_test_")
os.environ.setdefault("BROWSER_USER_DATA_DIR", f"{_TMP}/session")

from media.whatsapp.safety.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    """Tests for the per-contact sliding-window rate limiter."""

    def setUp(self):
        self.rl = RateLimiter(max_per_hour=3, cooldown_secs=60)

    def test_allows_initial_messages(self):
        self.assertTrue(self.rl.can_reply("Alice"))
        self.rl.record_reply("Alice")
        self.assertTrue(self.rl.can_reply("Alice"))
        self.rl.record_reply("Alice")
        self.assertTrue(self.rl.can_reply("Alice"))
        self.rl.record_reply("Alice")

    def test_blocks_after_limit(self):
        for _ in range(3):
            self.rl.record_reply("Alice")
        self.assertFalse(self.rl.can_reply("Alice"))

    def test_different_contacts_independent(self):
        for _ in range(3):
            self.rl.record_reply("Alice")
        self.assertFalse(self.rl.can_reply("Alice"))
        # Bob should still be allowed
        self.assertTrue(self.rl.can_reply("Bob"))

    def test_status_reporting(self):
        self.rl.record_reply("Alice")
        status = self.rl.status("Alice")
        self.assertEqual(status["contact"], "Alice")
        self.assertEqual(status["replies_last_hour"], 1)
        self.assertEqual(status["max_per_hour"], 3)
        self.assertFalse(status["blocked"])

    def test_blocked_status(self):
        for _ in range(3):
            self.rl.record_reply("Alice")
        status = self.rl.status("Alice")
        self.assertTrue(status["blocked"])
        self.assertGreater(status["blocked_until"], 0)

    def test_unblocked_after_cooldown(self):
        """After cooldown expires, the contact is unblocked.

        Note: the sliding-window limit (max_per_hour) still applies
        independently. To test cooldown in isolation, we use a large
        max_per_hour so the sliding window doesn't block us.
        """
        rl = RateLimiter(max_per_hour=100, cooldown_secs=0)
        # Record enough replies to trigger the cooldown
        # (cooldown triggers when len(dq) >= max_per_hour)
        for _ in range(100):
            rl.record_reply("Alice")
        # With cooldown_secs=0, blocked_until = now + 0 = now
        # After a tiny sleep, now > blocked_until, so the block is lifted
        time.sleep(0.01)
        # The sliding window is still full (100 replies in the last hour),
        # so can_reply returns False due to the window, not the cooldown.
        # To verify the COOLDOWN specifically, check status():
        status = rl.status("Alice")
        self.assertFalse(status["blocked"])  # cooldown expired

    def test_zero_max_blocks_after_first_reply(self):
        """Edge case: max_per_hour=0 means no replies allowed after any record.

        Before any reply is recorded, the deque is None so can_reply returns True.
        After recording one reply, len(dq)=0 and 0 < 0 is False.
        """
        rl = RateLimiter(max_per_hour=0, cooldown_secs=60)
        # Before any reply — allowed (deque is None)
        self.assertTrue(rl.can_reply("Anyone"))
        # After recording — blocked
        rl.record_reply("Anyone")
        self.assertFalse(rl.can_reply("Anyone"))


from media.whatsapp.safety.keywords import KeywordAlerts


class TestKeywordAlerts(unittest.TestCase):
    """Tests for the keyword alert system."""

    def setUp(self):
        # Patch the store to use a temp directory
        self._tmp = tempfile.mkdtemp(prefix="wabot_kw_")
        from media.whatsapp.memory.store import Store
        self._store = Store(self._tmp)
        self._patcher = patch("safety.keywords.store", self._store)
        self._patcher.start()
        self.ka = KeywordAlerts()

    def tearDown(self):
        self._patcher.stop()

    def test_no_keywords_no_match(self):
        """When no keywords are configured, nothing matches."""
        with patch.object(self.ka, "load", return_value=[]):
            alerts = self.ka.check("Alice", "hello world")
        self.assertEqual(alerts, [])

    def test_simple_match(self):
        with patch.object(self.ka, "load", return_value=["police", "money"]):
            alerts = self.ka.check("Alice", "I need to call the police")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["keyword"], "police")
        self.assertEqual(alerts[0]["contact"], "Alice")
        self.assertEqual(alerts[0]["risk_level"], "HIGH")

    def test_multiple_matches(self):
        with patch.object(self.ka, "load", return_value=["police", "money", "help"]):
            alerts = self.ka.check("Bob", "Send money or I call police for help")
        # "help" matches "help", "police" matches, "money" matches
        keywords = [a["keyword"] for a in alerts]
        self.assertIn("police", keywords)
        self.assertIn("money", keywords)
        self.assertIn("help", keywords)

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive. Each keyword produces one alert
        per check, regardless of how many times it appears in the text."""
        with patch.object(self.ka, "load", return_value=["police"]):
            alerts = self.ka.check("Alice", "POLICE POLICE Police")
        # One alert for the keyword "police" (matched once as a keyword)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["keyword"], "police")

    def test_no_match_in_empty_text(self):
        with patch.object(self.ka, "load", return_value=["police"]):
            alerts = self.ka.check("Alice", "")
        self.assertEqual(alerts, [])

    def test_no_match_in_none_text(self):
        with patch.object(self.ka, "load", return_value=["police"]):
            alerts = self.ka.check("Alice", None)
        self.assertEqual(alerts, [])

    def test_alert_log_capped(self):
        """Alert log should be capped to MAX_LOG_ENTRIES."""
        with patch.object(self.ka, "load", return_value=["trigger"]):
            for i in range(50):
                self.ka.check("Alice", f"trigger {i}")
        log = self.ka.get_log(limit=1000)
        self.assertLessEqual(len(log), self.ka.MAX_LOG_ENTRIES)
        self.assertGreater(len(log), 0)

    def test_get_log_respects_limit(self):
        with patch.object(self.ka, "load", return_value=["trigger"]):
            for i in range(10):
                self.ka.check("Alice", f"trigger {i}")
        log = self.ka.get_log(limit=5)
        self.assertEqual(len(log), 5)

    def test_webhook_called(self):
        webhook_calls = []
        self.ka.set_webhook(lambda event, data: webhook_calls.append((event, data)))
        with patch.object(self.ka, "load", return_value=["police"]):
            self.ka.check("Alice", "police")
        self.assertEqual(len(webhook_calls), 1)
        self.assertEqual(webhook_calls[0][0], "keyword_alert")
        self.assertEqual(webhook_calls[0][1]["keyword"], "police")

    def test_webhook_error_doesnt_crash(self):
        def failing_webhook(event, data):
            raise Exception("webhook down")
        self.ka.set_webhook(failing_webhook)
        with patch.object(self.ka, "load", return_value=["police"]):
            # Should not raise
            alerts = self.ka.check("Alice", "police")
        self.assertEqual(len(alerts), 1)  # alert still recorded


if __name__ == "__main__":
    unittest.main(verbosity=2)
