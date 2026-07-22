from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from xeno.computer_use.state_reader import ScreenState, ScreenElement

logger = logging.getLogger(__name__)


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    PRESS_KEY = "press_key"
    MOVE = "move"
    DRAG = "drag"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    OPEN_APP = "open_app"
    CLOSE_WINDOW = "close_window"


@dataclass
class PlannedAction:
    type: ActionType
    target: Optional[str] = None
    coordinates: Optional[tuple[int, int]] = None
    text: str = ""
    key: str = ""
    confidence: float = 0.0
    rationale: str = ""

    def __str__(self) -> str:
        base = f"[{self.type.value}]"
        if self.target:
            base += f" target={self.target}"
        if self.coordinates:
            base += f" at=({self.coordinates[0]},{self.coordinates[1]})"
        if self.text:
            base += f" text='{self.text[:40]}'"
        if self.key:
            base += f" key='{self.key}'"
        return base


class ActionPlanner:
    """Plans a sequence of computer use actions based on screen state and user goal.

    Given the current screen state and a user's goal, generates a step-by-step
    action plan. Uses vision model reasoning when available.
    """

    def __init__(self):
        self._llm = None

    def set_llm(self, llm: Any):
        self._llm = llm

    def find_element_by_text(self, state: ScreenState, text: str, partial: bool = True) -> Optional[ScreenElement]:
        text_lower = text.lower()
        for e in state.elements:
            if e.text:
                if partial and text_lower in e.text.lower():
                    return e
                if text_lower == e.text.lower():
                    return e
        return None

    def find_element_by_role(self, state: ScreenState, role: str) -> list[ScreenElement]:
        return [e for e in state.elements if e.role == role]

    async def plan_actions(self, goal: str, state: ScreenState) -> list[PlannedAction]:
        if self._llm:
            return await self._plan_with_llm(goal, state)

        return self._plan_heuristic(goal, state)

    async def _plan_with_llm(self, goal: str, state: ScreenState) -> list[PlannedAction]:
        try:
            state_summary = state.summary()
            prompt = (
                f"User goal: {goal}\n\n"
                f"Current screen state:\n{state_summary}\n\n"
                "Generate a step-by-step action plan. For each step, specify:\n"
                "- action type (click, type, press_key, scroll, wait, screenshot, move)\n"
                "- target element text or coordinates\n"
                "- text to type (if applicable)\n"
                "- key to press (if applicable)\n"
                "- why this step is needed\n\n"
                "Output as a JSON array of actions. Example:\n"
                '[{"type": "click", "target": "submit button", "rationale": "click submit"}, '
                '{"type": "type", "text": "hello", "target": "input field", "rationale": "enter text"}]'
            )
            result = await self._llm("You are a computer use action planner.", prompt)
            import json
            result_str = str(result)
            if "[" in result_str:
                json_str = result_str[result_str.index("["):result_str.rindex("]") + 1]
                actions_data = json.loads(json_str)
                actions = []
                for a in actions_data:
                    try:
                        actions.append(PlannedAction(
                            type=ActionType(a.get("type", "click")),
                            target=a.get("target", ""),
                            text=a.get("text", ""),
                            key=a.get("key", ""),
                            coordinates=tuple(a["coordinates"]) if "coordinates" in a else None,
                            confidence=0.7,
                            rationale=a.get("rationale", ""),
                        ))
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Action parse failed: {e}")
                return actions
        except Exception as e:
            logger.warning(f"LLM action planning failed: {e}")

        return self._plan_heuristic(goal, state)

    def _plan_heuristic(self, goal: str, state: ScreenState) -> list[PlannedAction]:
        actions = []
        goal_lower = goal.lower()

        if "click" in goal_lower or "press" in goal_lower or "select" in goal_lower:
            for kw in goal_lower.split():
                element = self.find_element_by_text(state, kw)
                if element:
                    cx = element.bounds[0] + element.bounds[2] // 2
                    cy = element.bounds[1] + element.bounds[3] // 2
                    actions.append(PlannedAction(
                        type=ActionType.CLICK,
                        target=element.text,
                        coordinates=(cx, cy),
                        confidence=0.6,
                        rationale=f"Click on '{element.text}'",
                    ))
                    return actions

        if "type" in goal_lower or "write" in goal_lower or "enter" in goal_lower:
            actions.append(PlannedAction(
                type=ActionType.CLICK,
                target="input field",
                confidence=0.5,
                rationale="Focus the input field first",
            ))

        if "scroll" in goal_lower:
            direction = 1 if "down" in goal_lower else -1
            actions.append(PlannedAction(
                type=ActionType.SCROLL,
                coordinates=(0, 0),
                text=str(direction * 3),
                confidence=0.7,
                rationale=f"Scroll {'down' if direction > 0 else 'up'}",
            ))

        if not actions:
            actions.append(PlannedAction(
                type=ActionType.SCREENSHOT,
                confidence=1.0,
                rationale="Take screenshot to understand current state",
            ))

        return actions
