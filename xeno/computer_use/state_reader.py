from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScreenElement:
    tag: str = ""
    text: str = ""
    role: str = ""
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    attributes: dict[str, str] = field(default_factory=dict)
    interactable: bool = False

    def __str__(self) -> str:
        parts = [f"[{self.role or self.tag}]"]
        if self.text:
            parts.append(f'"{self.text[:60]}"')
        parts.append(f"({self.bounds[0]},{self.bounds[1]} {self.bounds[2]}x{self.bounds[3]})")
        return " ".join(parts)


@dataclass
class ScreenState:
    elements: list[ScreenElement] = field(default_factory=list)
    focused_element: Optional[str] = None
    cursor_position: tuple[int, int] = (0, 0)
    screen_size: tuple[int, int] = (0, 0)
    active_window: str = ""
    error: str = ""

    def summary(self) -> str:
        interactable = [e for e in self.elements if e.interactable]
        lines = [
            f"Screen: {self.screen_size[0]}x{self.screen_size[1]}",
            f"Active window: {self.active_window}",
            f"Elements: {len(self.elements)} total, {len(interactable)} interactable",
        ]
        if interactable:
            lines.append("\nInteractable elements:")
            for e in interactable[:15]:
                lines.append(f"  {e}")
            if len(interactable) > 15:
                lines.append(f"  ... and {len(interactable) - 15} more")
        return "\n".join(lines)


class StateReader:
    """Reads current screen/application state as structured data.

    Combines multiple approaches:
    - Accessibility tree (via CDP or OS API)
    - OCR text blocks (via pytesseract)
    - Screenshot + vision model description
    - Window management API (via pygetwindow)
    """

    def __init__(self):
        self._vision_llm = None

    def set_vision_llm(self, llm: Any):
        self._vision_llm = llm

    async def read_state(self, screenshot_path: Optional[str] = None) -> ScreenState:
        state = ScreenState()

        # 1. Get screen size
        try:
            import pyautogui
            w, h = pyautogui.size()
            state.screen_size = (w, h)
        except Exception:
            pass

        # 2. Get active window
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                state.active_window = active.title
        except Exception:
            pass

        # 3. Get cursor position
        try:
            import pyautogui
            state.cursor_position = pyautogui.position()
        except Exception:
            pass

        # 4. OCR text from screenshot if available
        if screenshot_path and Path(screenshot_path).exists():
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(screenshot_path)
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                for i in range(len(data.get("text", []))):
                    text = data["text"][i]
                    if text and text.strip():
                        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                        state.elements.append(ScreenElement(
                            tag="text",
                            text=text.strip(),
                            role="text",
                            bounds=(x, y, w, h),
                            interactable=False,
                        ))
            except ImportError:
                logger.debug("pytesseract not available for OCR")
            except Exception as e:
                logger.warning(f"OCR failed: {e}")

        # 5. Vision model description if available
        if self._vision_llm and screenshot_path:
            try:
                description = await self._describe_with_vision(screenshot_path)
                if description:
                    state.elements.append(ScreenElement(
                        tag="vision",
                        text=description,
                        role="vision_description",
                        interactable=False,
                    ))
            except Exception as e:
                logger.warning(f"Vision description failed: {e}")

        return state

    async def _describe_with_vision(self, image_path: str) -> str:
        if not self._vision_llm:
            return ""
        try:
            import base64
            from pathlib import Path
            data = Path(image_path).read_bytes()
            b64 = base64.b64encode(data).decode()
            result = await self._vision_llm(
                "You are a computer vision assistant. Describe what you see on this screen. "
                "List all visible UI elements: buttons, text fields, links, labels, icons. "
                "Include their approximate positions (top, bottom, left, right).",
                f"Here is the screenshot (base64 image data): {b64[:500]}...\n"
                "Describe every visible UI element and its position.",
            )
            return str(result)[:2000]
        except Exception as e:
            logger.warning(f"Vision describe failed: {e}")
            return ""
