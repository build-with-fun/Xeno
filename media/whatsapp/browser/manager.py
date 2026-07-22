"""Browser lifecycle management: launch, persistent context, recovery.

Fixes the original code's issues:
- No detection of browser crash (Playwright would raise but bot would keep trying)
- No reconnection logic with backoff
- `headless=False` was hardcoded; no proxy support; no timezone/locale spoofing
"""
from __future__ import annotations

import random
import time
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import BrowserError
from media.whatsapp.human.fingerprint import build_init_script
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--start-maximized",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-notifications",
    "--no-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--enable-features=NetworkService",
]

# Detect Chrome profile sub-directory within the session dir
# (session_dir may not exist yet on first run — that's fine)
try:
    _sd = settings.session_dir
    if _sd.is_dir():
        if (_sd / "Default").is_dir():
            _BROWSER_ARGS.append("--profile-directory=Default")
        else:
            for child in _sd.iterdir():
                if child.name.startswith("Profile ") and child.is_dir():
                    _BROWSER_ARGS.append(f"--profile-directory={child.name}")
                    break
except (OSError, PermissionError, Exception):
    pass


class BrowserManager:
    """Manages the persistent Chromium context and main page."""

    def __init__(self) -> None:
        self._playwright = None
        self._context = None
        self._page = None
        self._init_script = build_init_script()

    @property
    def page(self):
        return self._page

    @property
    def context(self):
        return self._context

    def start(self) -> None:
        """Launch Playwright and open WhatsApp Web."""
        if self._page is not None:
            return  # already running
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise BrowserError("playwright not installed", transient=False) from e

        logger.info("[Browser] Starting Playwright + Chromium...")
        self._playwright = sync_playwright().start()

        launch_args = list(_BROWSER_ARGS)
        if settings.browser_proxy:
            launch_args.append(f"--proxy-server={settings.browser_proxy}")

        kwargs = dict(
            user_data_dir=str(settings.session_dir),
            headless=settings.browser_headless,
            no_viewport=True,
            args=launch_args,
        )
        # Timezone / locale spoofing
        if settings.browser_timezone:
            kwargs["timezone_id"] = settings.browser_timezone
        if settings.browser_locale:
            kwargs["locale"] = settings.browser_locale

        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                **kwargs
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "locked" in err_msg or "in use" in err_msg or "existing browser" in err_msg or "cannot be opened" in err_msg:
                fallback_dir = settings.data_dir / "whatsapp_profile_fallback"
                logger.warning(f"[Browser] Profile locked, trying fallback: {fallback_dir}")
                kwargs["user_data_dir"] = str(fallback_dir)
                fallback_dir.mkdir(parents=True, exist_ok=True)
                try:
                    self._context = self._playwright.chromium.launch_persistent_context(
                        **kwargs
                    )
                    logger.info(f"[Browser] Launched with fallback profile at {fallback_dir}")
                except Exception as e2:
                    logger.error(f"[Browser] Fallback also failed: {e2}")
                    raise BrowserError(f"Launch failed (profile locked, fallback also failed): {e2}", transient=False) from e2
            else:
                logger.error(f"[Browser] Launch failed: {e}")
                raise BrowserError(f"Launch failed: {e}", transient=False) from e

        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.add_init_script(self._init_script)
        self._page.set_default_timeout(30_000)

        logger.info("[Browser] Navigating to WhatsApp Web...")
        metrics.inc("browser_starts")
        try:
            self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        except Exception as e:
            logger.error(f"[Browser] Navigation failed: {e}")
            raise BrowserError(f"Navigation failed: {e}") from e

    def wait_for_whatsapp(self, timeout: int = 300) -> bool:
        """Wait for WhatsApp Web's #side element to appear."""
        logger.info("[WA] Waiting for WhatsApp Web to load (#side)...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                if self._page.query_selector("#side"):
                    logger.info("[WA] WhatsApp Web ready!")
                    return True
            except Exception:
                pass
            time.sleep(1)
        logger.error(f"[WA] Timed out after {timeout}s waiting for #side")
        return False

    def is_alive(self) -> bool:
        """Check if the browser and WhatsApp Web are still responsive."""
        if not self._page:
            return False
        try:
            return bool(self._page.query_selector("#side"))
        except Exception:
            return False

    def reload(self) -> bool:
        """Reload WhatsApp Web (e.g., after a disconnection)."""
        if not self._page:
            return False
        logger.warning("[WA] Reloading WhatsApp Web...")
        try:
            self._page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            ok = self.wait_for_whatsapp(timeout=120)
            if ok:
                metrics.inc("browser_reloads_success")
            else:
                metrics.inc("browser_reloads_failed")
            return ok
        except Exception as e:
            logger.error(f"[WA] Reload failed: {e}")
            metrics.inc("browser_reloads_failed")
            return False

    def stop(self) -> None:
        """Close the browser and stop Playwright."""
        logger.info("[Browser] Shutting down...")
        try:
            if self._context:
                self._context.close()
        except Exception as e:
            logger.warning(f"[Browser] Context close error: {e}")
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"[Browser] Playwright stop error: {e}")
        self._context = None
        self._page = None
        self._playwright = None
        logger.info("[Browser] Shutdown complete")


# Singleton
browser = BrowserManager()
