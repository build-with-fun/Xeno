"""Playwright browser — accessibility-tree based."""
from __future__ import annotations
import asyncio, logging
from pathlib import Path
from typing import Optional
logger = logging.getLogger(__name__)

class PlaywrightBrowser:
    def __init__(self, headless=True, screenshots_dir=None):
        self.headless = headless
        self.screenshots_dir = screenshots_dir or Path("data/browser_screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None; self._browser = None; self._page = None
    async def start(self):
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._page = await (await self._browser.new_context()).new_page()
            return True
        except ImportError:
            logger.warning("Playwright not installed")
            return False
    async def close(self):
        if self._browser: await self._browser.close()
        if self._playwright: await self._playwright.stop()
    async def navigate(self, url):
        if not self._page: await self.start()
        if self._page:
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return {"success": True, "url": url, "title": await self._page.title()}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Browser not started"}
    async def screenshot(self, path=None):
        if not self._page: return ""
        path = path or str(self.screenshots_dir / f"browser_{asyncio.get_event_loop().time():.0f}.png")
        await self._page.screenshot(path=path); return path
