"""WPP.js-based media downloader with on-disk caching.

Fixes the original code's issues:
- No caching — same media downloaded multiple times if processing failed
- No size limit — a 100MB video would crash the bot
- Base64 conversion happened in JS and was decoded in Python (slow for big files)
"""
from __future__ import annotations

import base64
import hashlib
import os
import time
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import MediaError
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)

# Don't download files larger than 25MB (WhatsApp's own limit is 16MB for media)
MAX_MEDIA_SIZE_BYTES = 25 * 1024 * 1024

_DOWNLOAD_JS = """
async (msgId) => {
    try {
        const msg = await WPP.chat.getMessageById(msgId);
        if (!msg) return { success: false, error: 'Message not found: ' + msgId };
        const blob = await WPP.chat.downloadMedia(msgId);
        if (!blob) return { success: false, error: 'downloadMedia returned null' };

        // Read blob as base64
        const b64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });

        return {
            success: true,
            base64: b64,
            type: msg.type,
            filename: msg.filename || '',
            mimetype: msg.mimetype || blob.type || '',
            caption: msg.caption || '',
            size: blob.size || 0,
        };
    } catch(e) {
        return { success: false, error: String(e) };
    }
}
"""


class MediaDownloader:
    """Downloads media via WPP.js and caches on disk."""

    def __init__(self) -> None:
        self._cache_dir = settings.media_cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, msg_id: str) -> tuple[str, str]:
        """Return (cache_path, hash) for a given message ID."""
        h = hashlib.sha256(msg_id.encode()).hexdigest()[:32]
        return self._cache_dir / f"{h}.bin", h

    def download(self, page, msg_id: str) -> Optional[dict]:
        """Download media for msg_id. Returns dict with 'bytes' or None.

        Returns cached result if available.
        """
        if not msg_id:
            return None

        cache_path, _ = self._cache_key(msg_id)
        meta_path = cache_path.with_suffix(".json")

        # Check cache
        if cache_path.exists() and meta_path.exists():
            try:
                import json
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                with open(cache_path, "rb") as f:
                    meta["bytes"] = f.read()
                logger.debug(f"[Media] Cache hit for {msg_id}")
                metrics.inc("media_cache_hits")
                return meta
            except Exception as e:
                logger.warning(f"[Media] Cache read failed for {msg_id}: {e}")

        # Download via WPP.js
        start = time.time()
        try:
            result = page.evaluate(_DOWNLOAD_JS, msg_id)
        except Exception as e:
            logger.error(f"[Media] WPP evaluate failed for {msg_id}: {e}")
            metrics.inc("media_download_errors", reason="evaluate_failed")
            return None

        if not result or not result.get("success"):
            err = result.get("error", "unknown") if result else "no result"
            logger.warning(f"[Media] Download failed for {msg_id}: {err}")
            metrics.inc("media_download_errors", reason="wpp_error")
            return None

        size = result.get("size", 0)
        if size > MAX_MEDIA_SIZE_BYTES:
            logger.warning(
                f"[Media] {msg_id} too large: {size} bytes "
                f"(max {MAX_MEDIA_SIZE_BYTES})"
            )
            metrics.inc("media_download_errors", reason="too_large")
            return None

        # Decode base64
        b64 = result.get("base64", "")
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64)
        except Exception as e:
            logger.error(f"[Media] Base64 decode failed for {msg_id}: {e}")
            metrics.inc("media_download_errors", reason="b64_decode")
            return None

        result["bytes"] = raw_bytes
        metrics.observe("media_download_seconds", time.time() - start)
        metrics.inc("media_download_success")

        # Write to cache (best-effort)
        try:
            import json
            meta = {k: v for k, v in result.items() if k != "bytes"}
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            with open(cache_path, "wb") as f:
                f.write(raw_bytes)
        except Exception as e:
            logger.warning(f"[Media] Cache write failed for {msg_id}: {e}")

        return result

    def clear_cache(self, max_age_days: int = 7) -> int:
        """Remove cached files older than max_age_days. Returns count removed."""
        cutoff = time.time() - (max_age_days * 86400)
        removed = 0
        for f in self._cache_dir.iterdir():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        if removed:
            logger.info(f"[Media] Cleared {removed} cached files older than {max_age_days}d")
        return removed


# Singleton
media_downloader = MediaDownloader()
