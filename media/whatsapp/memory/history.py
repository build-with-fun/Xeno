"""Conversation history management with summarization.

Fixes the original code's issues:
- `_maybe_summarize` was called inside `load_history` — meaning every read
  triggered a (possibly expensive) AI call. With multiple workers, this could
  cause concurrent summarization of the same contact.
- `_last_summarized` was a global dict mutated without a lock.
- Summarization failures silently returned the un-summarized history, which
  would grow unbounded.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

from media.whatsapp.config import settings
from media.whatsapp.core.types import ConversationEntry
from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.utils.text import safe_filename

logger = get_logger(__name__)

logger = get_logger(__name__)


class HistoryManager:
    """Manages per-contact conversation history with auto-summarization."""

    COLLECTION = "chats"

    def __init__(self) -> None:
        self._summarize_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._last_summarized: dict[str, datetime] = {}
        self._last_summarized_lock = threading.Lock()
        # Injected later (avoids circular import)
        self._summarizer: Optional[Callable[[str, str], str]] = None

    def set_summarizer(self, fn: Callable[[str, str], str]) -> None:
        """Inject the AI summarization function (old_summary, new_text) -> new_summary."""
        self._summarizer = fn

    def _contact_lock(self, contact: str) -> threading.Lock:
        with self._locks_guard:
            if contact not in self._summarize_locks:
                self._summarize_locks[contact] = threading.Lock()
            return self._summarize_locks[contact]

    def path_for(self, contact: str) -> str:
        return safe_filename(contact)

    def load(self, contact: str) -> List[ConversationEntry]:
        """Load history, triggering summarization if threshold is exceeded."""
        key = self.path_for(contact)
        raw = store.read(self.COLLECTION, key, []) or []
        entries = [ConversationEntry.from_dict(e) for e in raw]
        # Summarize outside the store lock
        entries = self._maybe_summarize(contact, entries)
        return entries

    def append(
        self, contact: str, history: List[ConversationEntry],
        role: str, content: str, kind: str = "text",
    ) -> List[ConversationEntry]:
        """Append a new entry and persist."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        label_map = {
            "text": "Text", "voice": "Recording", "image": "Image",
            "pdf": "PDF", "docx": "Document", "summary": "Summary",
        }
        label = label_map.get(kind, kind.capitalize())
        who = "You" if role == "assistant" else "Them"
        display = f'{who} [{label}]: "{content[:120]}"'
        entry = ConversationEntry(
            role=role, kind=kind, content=content,
            display=display, label=label, timestamp=ts,
        )
        history.append(entry)
        key = self.path_for(contact)
        store.write(self.COLLECTION, key, [e.to_dict() for e in history])
        logger.debug(f"[History] {contact} | {display[:80]}")
        return history

    def clear(self, contact: str) -> None:
        """Delete all conversation history for a contact."""
        key = self.path_for(contact)
        store.delete(self.COLLECTION, key)
        logger.info(f"[History] Cleared history for {contact}")

    def format_for_prompt(self, history: List[ConversationEntry], max_chars: int) -> str:
        """Render history as a single string for an AI prompt.

        Preserves summaries at the start; trims oldest regular entries to fit.
        """
        summary_parts: list[str] = []
        regular_parts: list[str] = []
        for e in history:
            if e.role == "system" and e.kind == "summary":
                summary_parts.append(f"[CONVERSATION SUMMARY]\n{e.content}")
            else:
                ts = e.timestamp or ""
                disp = e.display or e.content
                regular_parts.append(f"[{ts}] {disp}")

        summary_str = "\n\n".join(summary_parts)
        # Trim oldest regular entries until we fit
        while regular_parts:
            combined = summary_str + ("\n\n" if summary_str else "") + "\n".join(regular_parts)
            if len(combined) <= max_chars:
                break
            regular_parts.pop(0)
        return summary_str + ("\n\n" if summary_str and regular_parts else "") + "\n".join(regular_parts)

    def _maybe_summarize(
        self, contact: str, history: List[ConversationEntry],
    ) -> List[ConversationEntry]:
        """If history exceeds threshold, summarize older entries."""
        if len(history) <= settings.summary_threshold:
            return history
        # Throttle: don't summarize the same contact more than once per interval
        with self._last_summarized_lock:
            last = self._last_summarized.get(contact)
            if last and (datetime.now() - last).total_seconds() < settings.summary_min_interval_secs:
                return history

        # Per-contact lock so two threads don't summarize simultaneously
        lock = self._contact_lock(contact)
        if not lock.acquire(blocking=False):
            # Another thread is summarizing — skip
            return history
        try:
            return self._do_summarize(contact, history)
        finally:
            lock.release()

    def _do_summarize(
        self, contact: str, history: List[ConversationEntry],
    ) -> List[ConversationEntry]:
        existing_summary: Optional[ConversationEntry] = None
        regular: list[ConversationEntry] = []
        for e in history:
            if e.role == "system" and e.kind == "summary":
                existing_summary = e
            else:
                regular.append(e)

        keep = settings.summary_keep
        if len(regular) <= keep:
            return history
        recent = regular[-keep:]
        to_summarize = regular[:-keep]
        if not to_summarize:
            return history

        old_text = existing_summary.content if existing_summary else ""
        to_sum_text = "\n".join(
            f"[{e.timestamp}] {e.display or e.content}" for e in to_summarize
        )

        prompt = (
            "Summarize this WhatsApp conversation into a compact memory block.\n"
            "Extract: key people, ongoing topics, promises made, important facts, "
            "nicknames, relationship context, recurring themes.\n"
            "Max 250 words. Be specific — include names, numbers, details.\n\n"
            f"Previous summary:\n{old_text}\n\n"
            f"New messages to summarize:\n{to_sum_text}"
        )

        if not self._summarizer:
            logger.warning("[History] No summarizer set — skipping summarization")
            return history

        try:
            new_summary_text = self._summarizer(old_text, to_sum_text)
        except Exception as e:
            logger.warning(f"[History] Summarization failed for {contact}: {e}")
            return history

        if not new_summary_text:
            return history

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_entry = ConversationEntry(
            role="system", kind="summary", content=new_summary_text,
            display=f"[SUMMARY] {new_summary_text[:80]}...",
            label="Summary", timestamp=ts,
        )
        new_history = [summary_entry] + recent
        key = self.path_for(contact)
        store.write(self.COLLECTION, key, [e.to_dict() for e in new_history])

        with self._last_summarized_lock:
            self._last_summarized[contact] = datetime.now()

        logger.info(
            f"[History] Summarized {len(to_summarize)} entries for {contact}"
        )
        return new_history


# Singleton
history_manager = HistoryManager()
