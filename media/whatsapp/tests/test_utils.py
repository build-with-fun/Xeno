"""Unit tests for the utils module.

Run with: `python -m pytest tests/test_utils.py -v`
Or:        `python tests/test_utils.py`
"""
import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media.whatsapp.utils.text import safe_filename, truncate, normalize_whitespace, strip_markdown
from media.whatsapp.utils.crypto import hmac_sign, verify_hmac
from media.whatsapp.utils.time import now_iso, parse_iso, seconds_until, format_duration


class TestSafeFilename(unittest.TestCase):
    """Tests for safe_filename — the function that had a path-traversal bug in v1."""

    def test_normal_name(self):
        self.assertEqual(safe_filename("Alice"), "Alice")

    def test_spaces_replaced(self):
        self.assertEqual(safe_filename("Alice Smith"), "Alice_Smith")

    def test_special_chars_replaced(self):
        self.assertEqual(safe_filename("Alice@Smith#123"), "Alice_Smith_123")

    def test_path_traversal_blocked(self):
        """Critical: v1 allowed '../' through the regex."""
        result = safe_filename("../../../etc/passwd")
        self.assertNotIn("..", result)
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)

    def test_double_dot_blocked(self):
        result = safe_filename("..secret")
        self.assertNotIn("..", result)

    def test_empty_input(self):
        self.assertEqual(safe_filename(""), "unknown")
        self.assertEqual(safe_filename(None), "unknown")

    def test_null_byte_removed(self):
        result = safe_filename("alice\x00admin")
        self.assertNotIn("\x00", result)

    def test_unicode_normalized(self):
        result = safe_filename("Álice")
        # Should be ASCII-normalized
        self.assertNotIn("Á", result)

    def test_max_length(self):
        long_name = "A" * 200
        result = safe_filename(long_name, max_len=50)
        self.assertLessEqual(len(result), 50)


class TestTruncate(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(truncate("hello", 10), "hello")

    def test_exact_length(self):
        self.assertEqual(truncate("hello", 5), "hello")

    def test_truncated_with_suffix(self):
        self.assertEqual(truncate("hello world", 8), "hello w…")

    def test_custom_suffix(self):
        self.assertEqual(truncate("hello world", 8, suffix="..."), "hello...")


class TestNormalizeWhitespace(unittest.TestCase):
    def test_collapses_spaces(self):
        self.assertEqual(normalize_whitespace("a   b   c"), "a b c")

    def test_collapses_newlines(self):
        self.assertEqual(normalize_whitespace("a\n\n\nb"), "a b")

    def test_strips_ends(self):
        self.assertEqual(normalize_whitespace("  hello  "), "hello")


class TestStripMarkdown(unittest.TestCase):
    def test_removes_bold(self):
        self.assertEqual(strip_markdown("**bold**"), "bold")

    def test_removes_italic(self):
        self.assertEqual(strip_markdown("*italic*"), "italic")

    def test_removes_code_block(self):
        self.assertEqual(strip_markdown("```code```"), "")

    def test_removes_inline_code(self):
        self.assertEqual(strip_markdown("use `print()` now"), "use print() now")

    def test_removes_links(self):
        self.assertEqual(strip_markdown("[click](http://x)"), "click")

    def test_removes_headers(self):
        self.assertEqual(strip_markdown("# Title"), "Title")

    def test_removes_list_markers(self):
        self.assertEqual(strip_markdown("- item"), "item")


class TestHmac(unittest.TestCase):
    def test_sign_and_verify(self):
        sig = hmac_sign("secret", "payload")
        self.assertTrue(sig.startswith("sha256="))
        self.assertTrue(verify_hmac("secret", "payload", sig))

    def test_wrong_secret_fails(self):
        sig = hmac_sign("secret", "payload")
        self.assertFalse(verify_hmac("wrong", "payload", sig))

    def test_wrong_payload_fails(self):
        sig = hmac_sign("secret", "payload")
        self.assertFalse(verify_hmac("secret", "wrong", sig))

    def test_empty_inputs(self):
        self.assertFalse(verify_hmac("", "payload", "sha256=x"))
        self.assertFalse(verify_hmac("secret", "payload", ""))

    def test_bytes_payload(self):
        sig = hmac_sign("secret", b"payload")
        self.assertTrue(verify_hmac("secret", b"payload", sig))


class TestTimeUtils(unittest.TestCase):
    def test_now_iso_returns_string(self):
        result = now_iso()
        self.assertIsInstance(result, str)
        self.assertIn("T", result)

    def test_parse_iso_valid(self):
        dt = parse_iso("2025-01-15T10:30:00+05:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2025)

    def test_parse_iso_invalid(self):
        self.assertIsNone(parse_iso(""))
        self.assertIsNone(parse_iso("not-a-date"))
        self.assertIsNone(parse_iso(None))

    def test_format_duration_ms(self):
        self.assertEqual(format_duration(0.5), "500ms")

    def test_format_duration_seconds(self):
        self.assertEqual(format_duration(45), "45s")

    def test_format_duration_minutes(self):
        self.assertEqual(format_duration(125), "2m 5s")

    def test_format_duration_hours(self):
        self.assertEqual(format_duration(3725), "1h 2m 5s")

    def test_format_duration_days(self):
        self.assertEqual(format_duration(90061), "1d 1h 1m")


if __name__ == "__main__":
    unittest.main(verbosity=2)
