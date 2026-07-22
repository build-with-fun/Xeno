"""Computer Use — vision-driven screen interaction."""
from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
logger = logging.getLogger(__name__)

@dataclass
class ScreenElement:
    label: str; element_type: str = "button"
    center: tuple = (0,0); bbox: tuple = (0,0,0,0); confidence: float = 0.5

@dataclass
class ComputerUseResult:
    success: bool; action_taken: str = ""; reasoning: str = ""
    error: str = ""; iterations: int = 0

class ComputerUse:
    def __init__(self, screenshot_fn, click_fn, type_fn, key_fn,
                 vision_llm=None, screen_size_fn=None, max_iterations=10):
        self.screenshot_fn=screenshot_fn; self.click_fn=click_fn; self.type_fn=type_fn
        self.key_fn=key_fn; self.vision_llm=vision_llm
        self.screen_size_fn=screen_size_fn; self.max_iterations=max_iterations
    async def execute_task(self, task):
        if not self.vision_llm:
            return ComputerUseResult(False, error="No vision LLM available")
        screenshot = self.screenshot_fn()
        for i in range(self.max_iterations):
            try:
                prompt = f"Task: {task}\n\nLook at the screenshot. Decide NEXT action.\nNEXT_ACTION: click <desc> | type <desc> <text> | key <key> | DONE <summary>\nREASONING: <one sentence>"
                result = await self.vision_llm(screenshot, prompt)
                action, reasoning = self._parse(result)
                if action is None:
                    return ComputerUseResult(False, iterations=i+1, error=f"Parse failed: {result[:200]}")
                if action[0] == "DONE":
                    return ComputerUseResult(True, iterations=i+1, reasoning=action[1])
                if action[0] == "click":
                    await self.click_element(action[1])
                elif action[0] == "type":
                    await self.type_into(action[1], action[2])
                elif action[0] == "key":
                    self.key_fn(action[1])
                await asyncio.sleep(0.5)
                screenshot = self.screenshot_fn()
            except Exception as e:
                return ComputerUseResult(False, iterations=i+1, error=str(e))
        return ComputerUseResult(False, iterations=self.max_iterations, error="Max iterations")
    async def click_element(self, desc):
        # Simplified — in production would use vision to find element
        pass
    async def type_into(self, desc, text):
        pass
    def _parse(self, result):
        action = None; reasoning = ""
        for line in result.split("\n"):
            line = line.strip()
            if line.startswith("NEXT_ACTION:"):
                s = line[len("NEXT_ACTION:"):].strip()
                if s.startswith("DONE"): action = ("DONE", s[4:].strip())
                elif s.startswith("click"): action = ("click", s[5:].strip())
                elif s.startswith("type"):
                    parts = s[4:].strip().split(maxsplit=1)
                    action = ("type", parts[0], parts[1]) if len(parts)==2 else None
                elif s.startswith("key"): action = ("key", s[3:].strip())
            elif line.startswith("REASONING:"): reasoning = line[len("REASONING:"):].strip()
        return action, reasoning
