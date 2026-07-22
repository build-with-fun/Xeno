"""Agent-native computer use — transforms desktop control into structured,
machine-readable interactions instead of brittle pixel-based automation.

GUI mode: pyautogui + screenshots + vision (keep existing)
CLI-native mode: structured commands + machine-readable state feedback
CDP mode: Chrome DevTools Protocol for direct browser control
"""

from xeno.computer_use.cdp_bridge import CDPBridge, get_cdp_bridge
from xeno.computer_use.state_reader import StateReader
from xeno.computer_use.action_planner import ActionPlanner
