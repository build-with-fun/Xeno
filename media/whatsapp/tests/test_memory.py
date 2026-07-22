"""Tests for memory/ — store, seen tracker, personas, history.

These tests use temp directories to avoid polluting the real data/ folder.
"""
import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStore(unittest.TestCase):
    """Tests for the atomic JSON store."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="wabot_store_")
        from media.whatsapp.memory.store import Store
        self.store = Store(self._tmp)

    def test_read_missing_returns_default(self):
        result = self.store.read("nonexistent", "key", default="fallback")
        self.assertEqual(result, "fallback")

    def test_write_then_read(self):
        self.store.write("collection", "key1", {"name": "Alice", "age": 30})
        result = self.store.read("collection", "key1")
        self.assertEqual(result["name"], "Alice")
        self.assertEqual(result["age"], 30)

    def test_overwrite(self):
        self.store.write("c", "k", {"v": 1})
        self.store.write("c", "k", {"v": 2})
        result = self.store.read("c", "k")
        self.assertEqual(result["v"], 2)

    def test_delete(self):
        self.store.write("c", "k", {"v": 1})
        self.assertTrue(self.store.delete("c", "k"))
        # Second delete returns False
        self.assertFalse(self.store.delete("c", "k"))

    def test_delete_missing(self):
        self.assertFalse(self.store.delete("c", "never_existed"))

    def test_list_keys(self):
        self.store.write("c", "alpha", {"v": 1})
        self.store.write("c", "beta", {"v": 2})
        self.store.write("c", "gamma", {"v": 3})
        keys = self.store.list_keys("c")
        self.assertEqual(keys, ["alpha", "beta", "gamma"])

    def test_list_keys_empty_collection(self):
        self.assertEqual(self.store.list_keys("nope"), [])

    def test_corrupt_file_quarantined(self):
        """A corrupt JSON file should be quarantined, not crash the reader."""
        path = self.store.path_for("c", "broken")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ this is not valid json", encoding="utf-8")
        # Read should return default, not raise
        result = self.store.read("c", "broken", default="safe")
        self.assertEqual(result, "safe")
        # The corrupt file should have been moved aside
        self.assertFalse(path.exists())

    def test_concurrent_writes_same_key(self):
        """Two threads writing the same key shouldn't corrupt each other."""
        import threading
        errors = []
        def writer(val):
            try:
                for _ in range(20):
                    self.store.write("c", "shared", {"v": val})
            except Exception as e:
                errors.append(e)
        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(2,))
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertEqual(errors, [])
        # Final value should be valid JSON (either 1 or 2)
        result = self.store.read("c", "shared")
        self.assertIn(result["v"], (1, 2))

    def test_read_raw_and_write_raw(self):
        """Test the raw-path variants for ad-hoc file locations."""
        path = Path(self._tmp) / "custom" / "file.json"
        self.store.write_raw(path, {"custom": True})
        result = self.store.read_raw(path)
        self.assertEqual(result["custom"], True)

    def test_delete_raw(self):
        path = Path(self._tmp) / "to_delete.json"
        self.store.write_raw(path, {"v": 1})
        self.assertTrue(self.store.delete_raw(path))
        self.assertFalse(self.store.delete_raw(path))


class TestSeenTracker(unittest.TestCase):
    """Tests for the dedup tracker."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="wabot_seen_")
        from media.whatsapp.memory.store import Store
        from media.whatsapp.memory import seen as seen_mod
        self._store = Store(self._tmp)
        # Patch the module-level path used by SeenTracker
        self._path_patcher = patch.object(seen_mod, "_SEEN_IDS_PATH", Path(self._tmp) / "seen.json")
        self._store_patcher = patch("memory.store.store", self._store)
        self._path_patcher.start()
        self._store_patcher.start()
        from media.whatsapp.memory.seen import SeenTracker
        self.tracker = SeenTracker(max_in_memory=100, ttl_hours=1)

    def tearDown(self):
        self._path_patcher.stop()
        self._store_patcher.stop()

    def test_empty_string_not_duplicate(self):
        self.assertFalse(self.tracker.is_duplicate(""))

    def test_mark_then_check(self):
        self.assertFalse(self.tracker.is_duplicate("msg_1"))
        self.tracker.mark_seen("msg_1")
        self.assertTrue(self.tracker.is_duplicate("msg_1"))

    def test_different_ids_independent(self):
        self.tracker.mark_seen("msg_1")
        self.assertFalse(self.tracker.is_duplicate("msg_2"))

    def test_persist_and_reload(self):
        self.tracker.mark_seen("msg_1")
        self.tracker.mark_seen("msg_2")
        self.tracker.flush()

        # Create a new tracker — should load from disk
        from media.whatsapp.memory.seen import SeenTracker
        tracker2 = SeenTracker(max_in_memory=100, ttl_hours=1)
        tracker2.load()
        self.assertTrue(tracker2.is_duplicate("msg_1"))
        self.assertTrue(tracker2.is_duplicate("msg_2"))

    def test_lru_eviction(self):
        """When max_in_memory is exceeded, oldest entries are evicted."""
        tracker = self.tracker
        tracker._max = 5  # small limit for testing
        for i in range(10):
            tracker.mark_seen(f"msg_{i}")
        # Not all can fit — but recent ones should still be there
        self.assertTrue(tracker.is_duplicate("msg_9"))
        self.assertTrue(tracker.is_duplicate("msg_8"))
        # Very old ones may have been evicted
        stats = tracker.stats()
        self.assertLessEqual(stats["in_memory_count"], 5)

    def test_stats(self):
        self.tracker.mark_seen("a")
        self.tracker.mark_seen("b")
        stats = self.tracker.stats()
        self.assertEqual(stats["in_memory_count"], 2)
        self.assertEqual(stats["ttl_hours"], 1.0)


class TestPersonaManager(unittest.TestCase):
    """Tests for persona management."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="wabot_persona_")
        from media.whatsapp.memory.store import Store
        self._store = Store(self._tmp)
        # Patch BOTH the module-level store in personas AND the global store.
        # personas.py did `from memory.store import store` at import time,
        # so it holds its own reference that must be patched directly.
        self._personas_store_patcher = patch("memory.personas.store", self._store)
        self._personas_store_patcher.start()
        from media.whatsapp.memory.personas import PersonaManager
        self.pm = PersonaManager()

    def tearDown(self):
        self._personas_store_patcher.stop()

    def test_global_persona_created(self):
        """A default global persona should be created on init."""
        data = self._store.read("personas", "_global")
        self.assertIsNotNone(data)
        self.assertIn("name", data)

    def test_get_global_persona(self):
        from media.whatsapp.core.types import Persona
        p = self.pm.get()
        self.assertIsInstance(p, Persona)
        self.assertEqual(p.name, "Alex")  # default

    def test_set_global_persona(self):
        from media.whatsapp.core.types import Persona
        self.pm.set_global(Persona(name="TestBot", age=99))
        p = self.pm.get()
        self.assertEqual(p.name, "TestBot")
        self.assertEqual(p.age, 99)

    def test_contact_persona_overrides_global(self):
        from media.whatsapp.core.types import Persona
        self.pm.set_global(Persona(name="Global", language="English"))
        self.pm.set_contact("Alice", Persona(name="AliceBot", language="Urdu"))
        p = self.pm.get("Alice")
        self.assertEqual(p.name, "AliceBot")
        self.assertEqual(p.language, "Urdu")

    def test_contact_persona_partial_override(self):
        """Contact persona can override just some fields."""
        from media.whatsapp.core.types import Persona
        self.pm.set_global(Persona(name="Global", age=25, language="English"))
        # Contact only sets name — other fields should come from global
        self.pm.set_contact("Bob", Persona(name="BobBot"))
        p = self.pm.get("Bob")
        self.assertEqual(p.name, "BobBot")
        self.assertEqual(p.age, 25)  # from global
        self.assertEqual(p.language, "English")  # from global

    def test_no_contact_persona_returns_global(self):
        from media.whatsapp.core.types import Persona
        self.pm.set_global(Persona(name="Global"))
        p = self.pm.get("UnknownContact")
        self.assertEqual(p.name, "Global")


class TestHistoryManager(unittest.TestCase):
    """Tests for conversation history."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="wabot_hist_")
        from media.whatsapp.memory.store import Store
        self._store = Store(self._tmp)
        # Patch the store reference inside history.py (it did
        # `from memory.store import store` at import time, so it holds
        # its own reference).
        self._history_store_patcher = patch("memory.history.store", self._store)
        self._history_store_patcher.start()
        from media.whatsapp.memory.history import HistoryManager
        self.hm = HistoryManager()

    def tearDown(self):
        self._history_store_patcher.stop()

    def test_load_empty(self):
        history = self.hm.load("NewContact")
        self.assertEqual(history, [])

    def test_append_and_load(self):
        history = self.hm.load("Alice")
        history = self.hm.append("Alice", history, "user", "Hello", "text")
        history = self.hm.append("Alice", history, "assistant", "Hi there", "text")
        loaded = self.hm.load("Alice")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].role, "user")
        self.assertEqual(loaded[0].content, "Hello")
        self.assertEqual(loaded[1].role, "assistant")
        self.assertEqual(loaded[1].content, "Hi there")

    def test_format_for_prompt_short(self):
        history = self.hm.load("Alice")
        history = self.hm.append("Alice", history, "user", "Hi", "text")
        history = self.hm.append("Alice", history, "assistant", "Hello", "text")
        formatted = self.hm.format_for_prompt(history, max_chars=1000)
        self.assertIn("Hi", formatted)
        self.assertIn("Hello", formatted)

    def test_format_for_prompt_trims_old(self):
        """When history exceeds max_chars, oldest entries are dropped."""
        history = self.hm.load("Alice")
        for i in range(20):
            history = self.hm.append(
                "Alice", history, "user", f"Message number {i} " * 10, "text",
            )
        formatted = self.hm.format_for_prompt(history, max_chars=200)
        self.assertLessEqual(len(formatted), 200 + 50)  # small buffer

    def test_format_includes_summary(self):
        from media.whatsapp.core.types import ConversationEntry
        history = [
            ConversationEntry(
                role="system", kind="summary",
                content="Alice is a colleague from work",
                display="[SUMMARY]", label="Summary", timestamp="2025-01-01",
            ),
            ConversationEntry(
                role="user", kind="text", content="Hello",
                display="Them [Text]: Hello", label="Text", timestamp="2025-01-01",
            ),
        ]
        formatted = self.hm.format_for_prompt(history, max_chars=1000)
        self.assertIn("CONVERSATION SUMMARY", formatted)
        self.assertIn("Alice is a colleague", formatted)
        self.assertIn("Hello", formatted)

    def test_no_summarizer_set(self):
        """Without a summarizer, history is returned as-is even if long."""
        from media.whatsapp.config import settings
        # Temporarily lower the threshold so summarization would trigger
        with patch.object(settings, "summary_threshold", 2):
            with patch.object(settings, "summary_keep", 1):
                with patch.object(settings, "summary_min_interval_secs", 0):
                    history = self.hm.load("Alice")
                    for i in range(5):
                        history = self.hm.append("Alice", history, "user", f"msg {i}", "text")
                    # No summarizer set — should return all 5
                    loaded = self.hm.load("Alice")
                    self.assertEqual(len(loaded), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
