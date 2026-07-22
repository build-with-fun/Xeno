"""Atomic, thread-safe JSON file store.

Fixes the original code's issues:
- `atomic_write` used `os.rename` which fails on Windows if target exists
- No locking — concurrent writes from multiple threads could lose data
- No corruption recovery — a half-written file would crash JSON parsing
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class Store:
    """Thread-safe JSON key-value store backed by files.

    Each "collection" is a directory; each "key" is a JSON file in that directory.
    All writes are atomic (write to .tmp, fsync, rename) and protected by a
    per-key lock to prevent concurrent writers from clobbering each other.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _key_lock(self, path: str) -> threading.Lock:
        """Get (or create) a per-path lock."""
        with self._locks_guard:
            if path not in self._locks:
                self._locks[path] = threading.Lock()
            return self._locks[path]

    def path_for(self, collection: str, key: str) -> Path:
        """Return the full path for a collection/key pair."""
        return self.root / collection / f"{key}.json"

    def read(self, collection: str, key: str, default: Any = None) -> Any:
        """Read and parse a JSON file. Returns `default` on any failure."""
        path = self.path_for(collection, key)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[Store] Read failed for {path}: {e}")
            # If the file is corrupt, move it aside so future writes succeed
            self._quarantine(path)
            return default

    def write(self, collection: str, key: str, data: Any) -> None:
        """Atomically write `data` as JSON to collection/key.json."""
        path = self.path_for(collection, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._key_lock(str(path))
        with lock:
            tmp = path.with_suffix(path.suffix + ".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                # On POSIX, rename is atomic. On Windows, must remove target first.
                if os.name == "nt" and path.exists():
                    path.unlink()
                os.replace(tmp, path)
            except Exception as e:
                logger.error(f"[Store] Write failed for {path}: {e}")
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
                raise

    def delete(self, collection: str, key: str) -> bool:
        """Delete a key. Returns True if deleted, False if not found."""
        path = self.path_for(collection, key)
        lock = self._key_lock(str(path))
        with lock:
            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False

    def list_keys(self, collection: str) -> list[str]:
        """List all keys in a collection (without the .json suffix)."""
        d = self.root / collection
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json") if p.is_file())

    def read_raw(self, path: Path, default: Any = None) -> Any:
        """Read an arbitrary JSON file (for ad-hoc paths outside the store root)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return default

    def write_raw(self, path: Path, data: Any) -> None:
        """Atomically write to an arbitrary path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._key_lock(str(path))
        with lock:
            tmp = path.with_suffix(path.suffix + ".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                if os.name == "nt" and path.exists():
                    path.unlink()
                os.replace(tmp, path)
            except Exception as e:
                logger.error(f"[Store] Write failed for {path}: {e}")
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                raise

    def delete_raw(self, path: Path) -> bool:
        lock = self._key_lock(str(path))
        with lock:
            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False

    @staticmethod
    def _quarantine(path: Path) -> None:
        """Move a corrupt file to <name>.corrupt-<timestamp> for later inspection."""
        try:
            import time
            ts = int(time.time())
            dest = path.with_suffix(f".corrupt-{ts}")
            path.rename(dest)
            logger.warning(f"[Store] Quarantined corrupt file: {path} -> {dest}")
        except Exception:
            pass


# Singleton store rooted at data/
from media.whatsapp.config import settings
store = Store(settings.data_dir)
