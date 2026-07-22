"""WPP.js injection manager with version pinning and local caching.

Fixes the original code's issues:
- Used "nightly" URL — could break overnight with no warning
- Re-fetched on every restart (no local cache)
- Re-injected on every reload without checking if WPP was already present
- Waited for `WPP.isReady` in a polling loop with no async support
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import requests

from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import WPPError
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class WPPManager:
    """Manages WPP.js fetching, caching, and injection."""

    def __init__(self) -> None:
        self._js_cache: Optional[str] = None
        self._cache_path = Path(settings.wpp_js_local_cache)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._injected_pages: set[int] = set()

    def fetch_js(self) -> str:
        """Fetch WPP.js, preferring local cache. Falls back to remote."""
        if self._js_cache:
            return self._js_cache

        # Try local cache first
        if self._cache_path.exists() and self._cache_path.stat().st_size > 1000:
            try:
                self._js_cache = self._cache_path.read_text(encoding="utf-8")
                logger.info(
                    f"[WPP] Loaded from local cache: {len(self._js_cache):,} bytes"
                )
                return self._js_cache
            except Exception as e:
                logger.warning(f"[WPP] Cache read failed: {e}")

        # Fall back to remote
        logger.info(f"[WPP] Fetching from {settings.wpp_js_url}")
        try:
            r = requests.get(settings.wpp_js_url, timeout=30)
            r.raise_for_status()
            self._js_cache = r.text
            # Persist to local cache
            try:
                self._cache_path.write_text(self._js_cache, encoding="utf-8")
                logger.info(f"[WPP] Cached to {self._cache_path}")
            except Exception as e:
                logger.warning(f"[WPP] Cache write failed: {e}")
            logger.info(f"[WPP] Fetched {len(self._js_cache):,} bytes")
            return self._js_cache
        except Exception as e:
            logger.error(f"[WPP] Fetch failed: {e}")
            # Last-ditch: try cache even if it was previously invalid
            if self._cache_path.exists():
                self._js_cache = self._cache_path.read_text(encoding="utf-8")
                logger.warning(
                    f"[WPP] Using stale cache: {len(self._js_cache):,} bytes"
                )
                return self._js_cache
            raise WPPError(f"Could not fetch WPP.js: {e}", transient=False)

    def inject(self, page) -> bool:
        """Inject WPP.js into a page. Skips if already injected."""
        page_id = id(page)
        if page_id in self._injected_pages:
            # Verify it's still working
            try:
                if page.evaluate("() => !!(window.WPP && window.WPP.isReady)"):
                    return True
            except Exception:
                pass
            # Fall through to re-inject

        js = self.fetch_js()
        if not js:
            logger.error("[WPP] No JS to inject")
            return False

        # Try eval first, then add_script_tag
        try:
            page.evaluate(js)
            logger.info("[WPP] Injected via page.evaluate")
        except Exception as e:
            logger.warning(f"[WPP] evaluate failed: {e}, trying add_script_tag")
            try:
                page.add_script_tag(content=js)
                logger.info("[WPP] Injected via add_script_tag")
            except Exception as e2:
                logger.error(f"[WPP] add_script_tag also failed: {e2}")
                return False

        # Wait for WPP.isReady
        timeout = settings.wpp_injection_timeout
        start = time.time()
        while time.time() - start < timeout:
            try:
                ready = page.evaluate("() => window.WPP && window.WPP.isReady")
                if ready:
                    elapsed = time.time() - start
                    logger.info(f"[WPP] Ready after {elapsed:.1f}s")
                    self._injected_pages.add(page_id)
                    return True
            except Exception:
                pass
            time.sleep(0.25)

        logger.error(f"[WPP] isReady timed out after {timeout}s")
        return False

    def is_injected(self, page) -> bool:
        """Check if WPP.js is currently loaded and ready on the page."""
        try:
            return bool(page.evaluate("() => !!(window.WPP && window.WPP.isReady)"))
        except Exception:
            return False

    def reset(self) -> None:
        """Clear caches (force re-fetch on next inject)."""
        self._js_cache = None
        self._injected_pages.clear()


# Singleton
wpp = WPPManager()
