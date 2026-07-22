"""Desktop control tools — full PC automation (mouse, keyboard, screen, clipboard).

Uses pyautogui for mouse/keyboard control, works on Windows/Mac/Linux.
All tools are @tool decorated LangChain BaseTools.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Lazy-load pyautogui (it may not import on headless systems)
_PYAUTOGUI = None

def _get_pyautogui():
    global _PYAUTOGUI
    if _PYAUTOGUI is None:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        _PYAUTOGUI = pyautogui
    return _PYAUTOGUI


@tool
async def take_screenshot(region: str = "", describe: bool = False, ask: str = "") -> str:
    """Take a screenshot of the entire screen or a specific region.
    region format: 'x,y,width,height' (e.g. '100,200,800,600'). Empty for full screen.
    describe: if True, uses AI vision to describe the screenshot content.
    ask: optional specific question about the screenshot (ignored unless describe=True).
    Returns the path to the saved PNG file, plus a description if describe=True.
    """
    try:
        pag = _get_pyautogui()
        from xeno.config import XenoConfig
        config = XenoConfig.from_env()
        screenshot_dir = config.data_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = screenshot_dir / f"screenshot_{int(time.time())}.png"

        if region:
            parts = [int(p.strip()) for p in region.split(",")]
            if len(parts) == 4:
                img = pag.screenshot(region=tuple(parts))
            else:
                return f"Invalid region format. Use: x,y,width,height"
        else:
            img = pag.screenshot()

        img.save(str(path))
        result = f"Screenshot saved: {path} ({img.size[0]}x{img.size[1]})"

        if describe:
            try:
                import base64, io
                from xeno.tools.vision import _vision_ask
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=70)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                prompt = ask if ask else "Describe what you see on this screen in 2-3 sentences. Focus on visible apps, content, and overall context."
                description = await _vision_ask(prompt, b64)
                result += f"\n\nVision description:\n{description}"
            except Exception as e:
                result += f"\n(Vision description unavailable: {e})"

        return result
    except ImportError:
        return "pyautogui not installed. Run: pip install pyautogui"
    except Exception as e:
        return f"Error taking screenshot: {e}"


@tool
def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """Click the mouse at screen coordinates (x, y).
    button: 'left', 'right', or 'middle'. clicks: number of clicks (2 for double-click).
    """
    try:
        pag = _get_pyautogui()
        pag.click(x, y, clicks=clicks, button=button)
        return f"Clicked {button} at ({x}, {y}) {clicks} time(s)"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error clicking: {e}"


@tool
def mouse_move(x: int, y: int, duration: float = 0.3) -> str:
    """Move the mouse cursor to screen coordinates (x, y). duration: seconds for smooth movement."""
    try:
        pag = _get_pyautogui()
        pag.moveTo(x, y, duration=duration)
        return f"Mouse moved to ({x}, {y})"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error moving mouse: {e}"


@tool
def mouse_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    """Drag the mouse from (x1, y1) to (x2, y2). Useful for dragging files, selecting text, etc."""
    try:
        pag = _get_pyautogui()
        pag.moveTo(x1, y1, duration=0.2)
        pag.dragTo(x2, y2, duration=duration)
        return f"Dragged from ({x1}, {y1}) to ({x2}, {y2})"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error dragging: {e}"


@tool
def mouse_scroll(clicks: int = -3) -> str:
    """Scroll the mouse wheel. Negative scrolls down, positive scrolls up. Default: -3 (down 3 clicks)."""
    try:
        pag = _get_pyautogui()
        pag.scroll(clicks)
        direction = "up" if clicks > 0 else "down"
        return f"Scrolled {direction} {abs(clicks)} clicks"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error scrolling: {e}"


@tool
def type_text(text: str, interval: float = 0.02) -> str:
    """Type text at the current cursor position. Supports Unicode characters.
    Use for typing in input fields, chat boxes, code editors, etc.
    """
    try:
        pag = _get_pyautogui()
        # Use write() instead of typewrite() for Unicode support
        pag.write(text, interval=interval)
        return f"Typed: {text[:100]}{'...' if len(text) > 100 else ''}"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error typing: {e}"


@tool
def press_key(key: str, presses: int = 1) -> str:
    """Press a keyboard key or key combination.
    Single keys: 'enter', 'tab', 'escape', 'space', 'backspace', 'delete', 'up', 'down', 'left', 'right'.
    Key combos: 'ctrl+c', 'ctrl+v', 'alt+tab', 'ctrl+shift+esc', 'win+d', 'ctrl+a'.
    Function keys: 'f1', 'f2', ..., 'f12'.
    """
    try:
        pag = _get_pyautogui()
        if "+" in key:
            # Key combination like ctrl+c, alt+tab
            keys = [k.strip() for k in key.split("+")]
            for _ in range(presses):
                pag.hotkey(*keys)
            return f"Pressed '{key}' {presses} time(s)"
        else:
            for _ in range(presses):
                pag.press(key)
            return f"Pressed '{key}' {presses} time(s)"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error pressing key: {e}"


@tool
def get_screen_size() -> str:
    """Get the screen resolution (width x height). Useful for calculating click coordinates."""
    try:
        pag = _get_pyautogui()
        size = pag.size()
        return f"Screen size: {size.width}x{size.height}"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error getting screen size: {e}"


@tool
def get_mouse_position() -> str:
    """Get the current mouse cursor position (x, y)."""
    try:
        pag = _get_pyautogui()
        pos = pag.position()
        return f"Mouse position: ({pos.x}, {pos.y})"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error getting mouse position: {e}"


@tool
def clipboard_copy(text: str) -> str:
    """Copy text to the system clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:100]}{'...' if len(text) > 100 else ''}"
    except ImportError:
        return "pyperclip not installed. Run: pip install pyperclip"
    except Exception as e:
        return f"Error copying to clipboard: {e}"


@tool
def clipboard_paste() -> str:
    """Read the current clipboard content."""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return "pyperclip not installed. Run: pip install pyperclip"
    except Exception as e:
        return f"Error reading clipboard: {e}"


@tool
def type_and_enter(text: str) -> str:
    """Type text and press Enter. Convenience tool for submitting forms, chat messages, search boxes."""
    try:
        pag = _get_pyautogui()
        pag.write(text, interval=0.02)
        pag.press("enter")
        return f"Typed and pressed Enter: {text[:100]}"
    except ImportError:
        return "pyautogui not installed"
    except Exception as e:
        return f"Error: {e}"


# Export all desktop tools
DESKTOP_TOOLS = [
    take_screenshot, mouse_click, mouse_move, mouse_drag, mouse_scroll,
    type_text, press_key, type_and_enter,
    get_screen_size, get_mouse_position,
    clipboard_copy, clipboard_paste,
]
