"""Browser automation tools — full web control using Playwright.

All tools use async Playwright (no sync-in-async bugs).
The browser stays open between calls (singleton).
Supports: navigation, clicking, typing, screenshots, JS execution, content extraction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Singleton browser state (async)
_browser_state: dict = {}

# Local profile directory — sessions survive Xeno restarts without touching Chrome's own profile
BROWSER_PROFILE_DIR = Path("data/browser_profile")


async def _get_page():
    """Get or create the Playwright browser page (singleton)."""
    if "page" not in _browser_state:
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            # Use launch_persistent_context to avoid --user-data-dir launch arg error
            profile_path = str(BROWSER_PROFILE_DIR.resolve())
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                channel="chrome",
                headless=False,
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            )
            page = context.pages[0] if context.pages else await context.new_page()
            _browser_state["pw"] = pw
            _browser_state["context"] = context
            _browser_state["page"] = page
            logger.info(f"Playwright browser started (profile: {profile_path})")
        except ImportError:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        except Exception as e:
            raise RuntimeError(f"Failed to start browser: {e}")
    return _browser_state["page"]


def _open_url_native(url: str) -> str:
    """Open a URL using the system browser (fallback when Playwright unavailable)."""
    try:
        import subprocess, sys, os
        if sys.platform == "win32":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.run(["open", url], check=True)
        else:
            subprocess.run(["xdg-open", url], check=True)
        return f"Opened {url} in system browser"
    except Exception as e:
        return f"Error opening URL: {e}"


@tool
async def browser_open(url: str) -> str:
    """Open a URL in the browser. Uses Playwright for full automation control.
    The browser stays open — you can click, type, screenshot after.
    """
    # Ensure URL has protocol
    if not url.startswith("http"):
        url = "https://" + url
    try:
        page = await _get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        return f"Opened: {url}\nTitle: {title}"
    except RuntimeError as e:
        # Playwright not available — fall back to system browser
        logger.warning(f"Playwright unavailable, using system browser: {e}")
        return _open_url_native(url)
    except Exception as e:
        return f"Error opening browser: {e}"


@tool
async def browser_click(selector: str) -> str:
    """Click an element on the current page using a CSS selector.
    Examples: 'button#submit', 'input.search', 'a[href="/about"]', 'text=Login'.
    """
    try:
        page = await _get_page()
        await page.click(selector, timeout=10000)
        return f"Clicked: {selector}"
    except Exception as e:
        return f"Error clicking '{selector}': {e}"


@tool
async def browser_type(selector: str, text: str, press_enter: bool = False) -> str:
    """Type text into an input field on the current page.
    selector: CSS selector for the input field (e.g. 'input#search', 'textarea[name=message]').
    text: the text to type.
    press_enter: if True, press Enter after typing (for search boxes, forms).
    """
    try:
        page = await _get_page()
        await page.fill(selector, text, timeout=10000)
        if press_enter:
            await page.press(selector, "Enter")
        action = "typed and pressed Enter" if press_enter else "typed"
        return f"{action} '{text[:50]}' into {selector}"
    except Exception as e:
        return f"Error typing into '{selector}': {e}"


@tool
async def browser_screenshot(describe: bool = False, ask: str = "") -> str:
    """Take a screenshot of the current browser page. Returns the path to the saved image.
    describe: if True, uses AI vision to describe the page content.
    ask: optional specific question about the page (ignored unless describe=True).
    """
    try:
        page = await _get_page()
        from xeno.config import XenoConfig
        config = XenoConfig.from_env()
        screenshot_dir = config.data_dir / "browser_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / f"browser_{int(time.time())}.png"
        await page.screenshot(path=str(path), full_page=False)
        result = f"Screenshot saved: {path}"

        if describe:
            try:
                import base64, io
                from PIL import Image as PILImage
                from xeno.tools.vision import _vision_ask
                img = PILImage.open(path)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=70)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                prompt = ask if ask else "Describe what you see on this web page in 2-3 sentences. Focus on the page content, visible elements, and overall layout."
                description = await _vision_ask(prompt, b64)
                result += f"\n\nPage description:\n{description}"
            except Exception as e:
                result += f"\n(Vision description unavailable: {e})"

        return result
    except Exception as e:
        return f"Error taking browser screenshot: {e}"


@tool
async def browser_get_content() -> str:
    """Get the text content of the current page. Returns up to 5000 characters."""
    try:
        page = await _get_page()
        text = await page.inner_text("body")
        return text[:5000] if text else "No text content found"
    except Exception as e:
        return f"Error getting page content: {e}"


@tool
async def browser_get_title() -> str:
    """Get the title of the current page."""
    try:
        page = await _get_page()
        title = await page.title()
        return f"Page title: {title}"
    except Exception as e:
        return f"Error getting title: {e}"


@tool
async def browser_get_url() -> str:
    """Get the current URL of the browser."""
    try:
        page = await _get_page()
        url = page.url
        return f"Current URL: {url}"
    except Exception as e:
        return f"Error getting URL: {e}"


@tool
async def browser_evaluate(js_code: str) -> str:
    """Execute JavaScript on the current page and return the result.
    Example: document.querySelectorAll('a').length
    """
    try:
        page = await _get_page()
        result = await page.evaluate(js_code)
        import json
        return json.dumps(result, indent=2, default=str)[:5000] if result else "Executed (no result)"
    except Exception as e:
        return f"Error executing JS: {e}"


@tool
async def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Scroll the page. direction: 'up' or 'down'. amount: pixels to scroll (default 500)."""
    try:
        page = await _get_page()
        if direction == "down":
            await page.mouse.wheel(0, amount)
        else:
            await page.mouse.wheel(0, -amount)
        return f"Scrolled {direction} {amount} pixels"
    except Exception as e:
        return f"Error scrolling: {e}"


@tool
async def browser_wait(seconds: float = 2.0) -> str:
    """Wait for a number of seconds (for pages to load, animations, etc.)."""
    try:
        await asyncio.sleep(seconds)
        return f"Waited {seconds} seconds"
    except Exception as e:
        return f"Error waiting: {e}"


@tool
async def browser_press_key(key: str) -> str:
    """Press a keyboard key on the browser page.
    Examples: 'Enter', 'Escape', 'Tab', 'ArrowDown', 'Control+a'.
    """
    try:
        page = await _get_page()
        await page.keyboard.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Error pressing key: {e}"


@tool
async def browser_close() -> str:
    """Close the browser and clean up resources (profile data is kept for next session)."""
    try:
        if "context" in _browser_state:
            await _browser_state["context"].close()
            await _browser_state["pw"].stop()
            _browser_state.clear()
            return f"Browser closed"
        return "Browser not open"
    except Exception as e:
        return f"Error closing browser: {e}"


# Export all browser tools
BROWSER_TOOLS = [
    browser_open, browser_click, browser_type, browser_screenshot,
    browser_get_content, browser_get_title, browser_get_url,
    browser_evaluate, browser_scroll, browser_wait, browser_press_key,
    browser_close,
]
