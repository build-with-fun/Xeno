import os
import sys
import io
import json
import math
import random
import base64
import subprocess
import tempfile
import asyncio
import time
import re
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional

from fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
import pyautogui
from PIL import ImageGrab, ImageDraw, Image
import pyperclip
import pygetwindow as gw
import psutil

mcp = FastMCP("Automation Agent Server")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKSPACE_DIR = str(PROJECT_ROOT)
AGENT_OUTPUT = str(PROJECT_ROOT / "agent_output")
os.makedirs(AGENT_OUTPUT, exist_ok=True)

# --- UTILITY HELPERS ---

def _screen_size():
    w, h = pyautogui.size()
    return w, h

def _bezier_path(start_x, start_y, end_x, end_y, steps=30, wobble=0.02):
    path = []
    cx1 = start_x + (end_x - start_x) * 0.3 + random.uniform(-50, 50)
    cy1 = start_y + random.uniform(-30, 30)
    cx2 = start_x + (end_x - start_x) * 0.7 + random.uniform(-50, 50)
    cy2 = end_y + random.uniform(-30, 30)
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * start_x + 3 * mt**2 * t * cx1 + 3 * mt * t**2 * cx2 + t**3 * end_x
        y = mt**3 * start_y + 3 * mt**2 * t * cy1 + 3 * mt * t**2 * cy2 + t**3 * end_y
        if wobble > 0:
            x += random.uniform(-wobble * abs(end_x - start_x), wobble * abs(end_x - start_x))
            y += random.uniform(-wobble * abs(end_y - start_y), wobble * abs(end_y - start_y))
        path.append((int(x), int(y)))
    return path

def _human_delay():
    time.sleep(random.uniform(0.05, 0.2))

def _smooth_move_to(x, y, duration=None):
    screen_w, screen_h = _screen_size()
    cx, cy = pyautogui.position()
    steps = random.randint(25, 45)
    if duration is None:
        duration = random.uniform(0.3, 0.8)
    path = _bezier_path(cx, cy, x, y, steps=steps)
    for px, py in path:
        pyautogui.moveTo(px, py, duration=0.0)
        time.sleep(duration / len(path))

# --- SCREEN CAPTURE & VISION ---

_os_node_map = {}

@mcp.tool()
def capture_screen() -> list:
    """
    Capture the full screen and return the image (compressed JPEG).
    Use this to see what's on the user's display.
    """
    try:
        img = ImageGrab.grab()
        w, h = img.size
        if max(w, h) > 1280:
            scale = 1280 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=60, optimize=True)
        b64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        return [ImageContent(type="image", data=b64, mimeType="image/jpeg")]
    except Exception as e:
        raise Exception(f"Failed to capture screen: {str(e)}")

@mcp.tool()
def capture_annotated_screen() -> list:
    """
    Capture screen with numbered bounding boxes over all interactive UI elements.
    Each element gets a unique ID. Use control_ui(element_id=ID) to interact with it.
    """
    try:
        img = ImageGrab.grab()
        draw = ImageDraw.Draw(img)
        global _os_node_map
        _os_node_map.clear()

        active = gw.getActiveWindow()
        if active:
            try:
                from pywinauto import Desktop
                win = Desktop(backend="uia").window(handle=active._hWnd)
                next_id = 1
                for ctrl in win.descendants():
                    try:
                        rect = ctrl.rectangle()
                        ctype = ctrl.element_info.control_type
                        text = ctrl.window_text()
                        if ctype in ['Button', 'Edit', 'MenuItem', 'ListItem', 'TabItem', 'Hyperlink', 'CheckBox', 'RadioButton', 'Text', 'Document', 'ComboBox', 'TreeItem', 'Spinner', 'Slider']:
                            if rect.width() > 0 and rect.height() > 0 and rect.width() < 2000 and rect.height() < 2000:
                                _os_node_map[next_id] = {
                                    'x': rect.mid_point().x,
                                    'y': rect.mid_point().y,
                                    'text': text,
                                    'type': ctype
                                }
                                x1, y1, x2, y2 = rect.left, rect.top, rect.right, rect.bottom
                                draw.rectangle([x1, y1, x2, y2], outline="#00FF88", width=2)
                                draw.rectangle([x1, y1-18, x1+24, y1], fill="#00FF88")
                                draw.text((x1+3, y1-16), str(next_id), fill="#000000")
                                next_id += 1
                    except:
                        pass
            except:
                pass

        w, h = img.size
        if max(w, h) > 1280:
            scale = 1280 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=65, optimize=True)
        b64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

        summary = f"Screen captured with {len(_os_node_map)} annotated elements. "
        summary += f"Active window: {active.title if active else 'None'}. "
        summary += "Use control_ui(element_id=ID) to interact."

        return [
            ImageContent(type="image", data=b64, mimeType="image/jpeg"),
            TextContent(type="text", text=summary)
        ]
    except Exception as e:
        raise Exception(f"Failed to capture annotated screen: {str(e)}")

# --- MOUSE CONTROL ---

@mcp.tool()
def mouse_move(x: int = None, y: int = None, x_pct: float = None, y_pct: float = None, smooth: bool = True) -> str:
    """
    Move the mouse to absolute coordinates or screen percentage.
    x, y: Absolute pixel coordinates
    x_pct, y_pct: Screen percentage (0.0-1.0), e.g. 0.5 = center
    smooth: Use smooth bezier movement (default True)
    """
    try:
        screen_w, screen_h = _screen_size()
        if x_pct is not None and y_pct is not None:
            x = int(screen_w * x_pct)
            y = int(screen_h * y_pct)
        if x is None or y is None:
            return "Error: Provide either (x,y) or (x_pct,y_pct)"
        if smooth:
            _smooth_move_to(x, y)
        else:
            pyautogui.moveTo(x, y)
        return f"Mouse moved to ({x}, {y})"
    except Exception as e:
        return f"Mouse move error: {str(e)}"

@mcp.tool()
def mouse_click(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    """
    Click the mouse at current position or specified coordinates.
    x, y: Optional absolute coordinates to click at
    button: 'left', 'right', 'middle' (default: 'left')
    clicks: Number of clicks - 1 (single), 2 (double) (default: 1)
    """
    try:
        if x is not None and y is not None:
            _smooth_move_to(x, y)
            _human_delay()
        btn = button.lower()
        if btn == "left":
            pyautogui.click(clicks=clicks)
        elif btn == "right":
            pyautogui.rightClick()
        elif btn == "middle":
            pyautogui.middleClick()
        elif btn == "double":
            pyautogui.doubleClick()
        else:
            pyautogui.click(button=btn, clicks=clicks)
        coord = f" at ({x},{y})" if x is not None else " at current position"
        return f"{button.title()} click{coord} executed"
    except Exception as e:
        return f"Mouse click error: {str(e)}"

@mcp.tool()
def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> str:
    """
    Drag the mouse from start position to end position smoothly.
    start_x, start_y: Starting pixel coordinates
    end_x, end_y: Ending pixel coordinates
    duration: Duration in seconds (default 0.5)
    """
    try:
        pyautogui.moveTo(start_x, start_y)
        _human_delay()
        pyautogui.dragTo(end_x, end_y, duration=duration, button='left')
        return f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})"
    except Exception as e:
        return f"Mouse drag error: {str(e)}"

@mcp.tool()
def mouse_scroll(clicks: int = 3, direction: str = "down") -> str:
    """
    Scroll the mouse wheel.
    clicks: Number of scroll clicks (default: 3)
    direction: 'up' or 'down' (default: 'down')
    """
    try:
        amount = clicks if direction == "up" else -clicks
        pyautogui.scroll(amount)
        return f"Scrolled {direction} {clicks} clicks"
    except Exception as e:
        return f"Scroll error: {str(e)}"

@mcp.tool()
def mouse_get_position() -> str:
    """Get the current mouse cursor position."""
    try:
        x, y = pyautogui.position()
        screen_w, screen_h = _screen_size()
        return f"Position: ({x}, {y}) | Screen: {screen_w}x{screen_h} | Percentage: ({x/screen_w:.3f}, {y/screen_h:.3f})"
    except Exception as e:
        return f"Position error: {str(e)}"

# --- KEYBOARD CONTROL ---

@mcp.tool()
def keyboard_type(text: str, wpm: int = 80) -> str:
    """
    Type text with human-like timing.
    text: The text to type
    wpm: Typing speed in words per minute (default 80)
    """
    try:
        interval = 60.0 / (wpm * 5.0)
        jitter = interval * 0.3
        for char in text:
            delay = interval + random.uniform(-jitter, jitter)
            delay = max(0.005, delay)
            pyautogui.write(char, interval=0.0)
            time.sleep(delay)
        return f"Typed {len(text)} characters at {wpm} wpm"
    except Exception as e:
        return f"Keyboard type error: {str(e)}"

@mcp.tool()
def keyboard_press(key: str) -> str:
    """
    Press a single keyboard key.
    key: Key name (e.g. 'enter', 'escape', 'tab', 'ctrl', 'alt', 'f5', 'shift',
          'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
          'backspace', 'delete', 'space', 'win')
    """
    try:
        pyautogui.press(key)
        return f"Pressed key: {key}"
    except Exception as e:
        return f"Keyboard press error: {str(e)}"

@mcp.tool()
def keyboard_hotkey(keys: str) -> str:
    """
    Press a keyboard shortcut / hotkey combination.
    keys: Comma-separated key names (e.g. 'ctrl,c' for Ctrl+C, 'ctrl,shift,esc' for Task Manager)
    """
    try:
        key_list = [k.strip() for k in keys.split(',')]
        pyautogui.hotkey(*key_list)
        return f"Executed hotkey: {keys}"
    except Exception as e:
        return f"Hotkey error: {str(e)}"

@mcp.tool()
def keyboard_write(text: str) -> str:
    """
    Write text instantly (faster than type_text, no human-like delay).
    text: The text to type
    """
    try:
        pyautogui.write(text, interval=0.0)
        return f"Wrote {len(text)} characters"
    except Exception as e:
        return f"Keyboard write error: {str(e)}"

# --- UI AUTOMATION (SMART CLICK / ANNOTATION) ---

@mcp.tool()
def control_ui(action: str, x: int = None, y: int = None, x_pct: float = None, y_pct: float = None,
               element_id: int = None,
               start_x_pct: float = None, start_y_pct: float = None,
               end_x_pct: float = None, end_y_pct: float = None,
               text: str = None, key: str = None,
               direction: str = None, amount: int = None, wpm: int = 80) -> str:
    """
    Universal UI controller. Actions:
    'click', 'right_click', 'double_click', 'move_to' - use element_id OR (x_pct,y_pct) OR (x,y)
    'drag_to' - drag to target coordinates
    'grab' - drag select from start_* to end_*
    'scroll' - scroll up/down by amount
    'type_text' - type text with human-like speed
    'press_key' - press a single key
    'hotkey' - press hotkey combination (comma-separated keys)
    """
    try:
        screen_w, screen_h = _screen_size()

        if element_id is not None:
            if element_id in _os_node_map:
                x = _os_node_map[element_id]['x']
                y = _os_node_map[element_id]['y']
            else:
                return f"Error: element_id {element_id} not found. Run capture_annotated_screen first."
        elif x_pct is not None and y_pct is not None:
            x = int(screen_w * x_pct)
            y = int(screen_h * y_pct)

        if action in ['click', 'right_click', 'double_click', 'move_to']:
            if x is not None and y is not None:
                _smooth_move_to(x, y)
                _human_delay()
            if action == 'click':
                if x is None: pyautogui.click()
                else: pyautogui.click(x=x, y=y)
            elif action == 'right_click':
                if x is None: pyautogui.rightClick()
                else: pyautogui.rightClick(x=x, y=y)
            elif action == 'double_click':
                if x is None: pyautogui.doubleClick()
                else: pyautogui.doubleClick(x=x, y=y)
            elif action == 'move_to':
                pass

        elif action == 'drag_to':
            if x is None or y is None: return "Error: target required."
            pyautogui.dragTo(x=x, y=y, duration=0.5, button='left')

        elif action == 'grab':
            if start_x_pct is None or end_x_pct is None:
                return "Error: start/end percentages required."
            sx = int(screen_w * start_x_pct)
            sy = int(screen_h * start_y_pct)
            ex = int(screen_w * end_x_pct)
            ey = int(screen_h * end_y_pct)
            pyautogui.moveTo(sx, sy)
            pyautogui.dragTo(ex, ey, duration=0.8, button='left')

        elif action == 'scroll':
            if not direction or not amount: return "Error: direction and amount required."
            clicks = amount if direction == 'up' else -amount
            pyautogui.scroll(clicks)

        elif action == 'type_text':
            if not text: return "Error: 'text' required."
            return keyboard_type(text, wpm=wpm)

        elif action == 'press_key':
            if not key: return "Error: 'key' required."
            pyautogui.press(key)

        elif action == 'hotkey':
            if not key: return "Error: 'key' (comma-separated) required."
            keys = [k.strip() for k in key.split(',')]
            pyautogui.hotkey(*keys)

        else:
            return f"Error: Unknown action '{action}'."

        return f"Executed UI action: {action}"
    except Exception as e:
        return f"Failed to execute UI action '{action}': {str(e)}"

@mcp.tool()
def desktop_inspect(title: str, max_elements: int = 100) -> str:
    """
    Inspect a native Windows application's UI element tree.
    title: Window title substring to search for
    max_elements: Maximum elements to return (default 100)
    """
    try:
        from pywinauto import Desktop
        app = Desktop(backend="uia").window(title_re=f".*{title}.*")
        if not app.exists():
            return f"Window matching '{title}' not found."

        output = []
        for ctrl in app.descendants():
            text = ctrl.window_text()
            ctrl_type = ctrl.element_info.control_type
            if text and ctrl_type not in ['Pane', 'Window']:
                rect = ctrl.rectangle()
                output.append(f"[{ctrl_type}] '{text}' at ({rect.left},{rect.top}) {rect.width()}x{rect.height()}")
            if len(output) >= max_elements:
                output.append("... truncated ...")
                break
        return "\n".join(output) if output else "No readable controls found."
    except Exception as e:
        return f"Inspect error: {str(e)}"

@mcp.tool()
def desktop_click(title: str, element_text: str) -> str:
    """
    Click a UI element in a Windows application by its text label.
    title: Window title substring
    element_text: Exact text of the element to click
    """
    try:
        from pywinauto import Desktop
        app = Desktop(backend="uia").window(title_re=f".*{title}.*")
        if not app.exists():
            return f"Window '{title}' not found."
        ctrl = app.child_window(title=element_text)
        if not ctrl.exists():
            return f"Element '{element_text}' not found."
        try:
            ctrl.invoke()
        except:
            ctrl.click_input()
        return f"Clicked '{element_text}' in '{title}'"
    except Exception as e:
        return f"Desktop click error: {str(e)}"

# --- CLIPBOARD ---

@mcp.tool()
def clipboard_read() -> str:
    """Read text from the system clipboard."""
    try:
        content = pyperclip.paste()
        return f"Clipboard ({len(content)} chars):\n{content[:2000]}"
    except Exception as e:
        return f"Clipboard read error: {str(e)}"

@mcp.tool()
def clipboard_write(text: str) -> str:
    """Write text to the system clipboard."""
    try:
        pyperclip.copy(text)
        return f"Copied {len(text)} characters to clipboard"
    except Exception as e:
        return f"Clipboard write error: {str(e)}"

@mcp.tool()
def clipboard_append(text: str) -> str:
    """Append text to the current clipboard content."""
    try:
        current = pyperclip.paste()
        pyperclip.copy(current + text)
        return f"Appended {len(text)} chars to clipboard"
    except Exception as e:
        return f"Clipboard append error: {str(e)}"

@mcp.tool()
def clipboard_clear() -> str:
    """Clear the system clipboard."""
    try:
        pyperclip.copy("")
        return "Clipboard cleared"
    except Exception as e:
        return f"Clipboard clear error: {str(e)}"

# --- FILE OPERATIONS ---

@mcp.tool()
def file_write(relative_path: str, content: str) -> str:
    """
    Write content to a file in agent_output/.
    relative_path: Path relative to agent_output/ (e.g. 'notes.txt', 'subdir/data.json')
    content: Text content to write
    """
    try:
        safe_path = os.path.normpath(os.path.join(AGENT_OUTPUT, relative_path))
        if not safe_path.startswith(os.path.normpath(AGENT_OUTPUT)):
            return f"Error: Path escapes agent_output/ directory."
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {safe_path}"
    except Exception as e:
        return f"File write error: {str(e)}"

@mcp.tool()
def file_read(relative_path: str) -> str:
    """
    Read content from a file in agent_output/.
    relative_path: Path relative to agent_output/
    """
    try:
        safe_path = os.path.normpath(os.path.join(AGENT_OUTPUT, relative_path))
        if not safe_path.startswith(os.path.normpath(AGENT_OUTPUT)):
            return f"Error: Path escapes agent_output/ directory."
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"File read error: {str(e)}"

@mcp.tool()
def file_list(directory: str = "") -> str:
    """
    List files in agent_output/ directory.
    directory: Subdirectory relative to agent_output/ (default: root)
    """
    try:
        target = os.path.normpath(os.path.join(AGENT_OUTPUT, directory))
        if not target.startswith(os.path.normpath(AGENT_OUTPUT)):
            return "Error: Path escapes agent_output/ directory."
        if not os.path.exists(target):
            return f"Directory not found: {target}"
        items = []
        for entry in os.scandir(target):
            items.append(f"{'[DIR]' if entry.is_dir() else '[FILE]'} {entry.name}")
        return "\n".join(sorted(items)) if items else "Directory is empty"
    except Exception as e:
        return f"File list error: {str(e)}"

@mcp.tool()
def file_delete(relative_path: str) -> str:
    """
    Delete a file in agent_output/.
    relative_path: Path relative to agent_output/
    """
    try:
        safe_path = os.path.normpath(os.path.join(AGENT_OUTPUT, relative_path))
        if not safe_path.startswith(os.path.normpath(AGENT_OUTPUT)):
            return "Error: Path escapes agent_output/ directory."
        if os.path.isfile(safe_path):
            os.remove(safe_path)
            return f"Deleted: {relative_path}"
        elif os.path.isdir(safe_path):
            os.rmdir(safe_path)
            return f"Deleted empty directory: {relative_path}"
        return f"Not found: {relative_path}"
    except Exception as e:
        return f"File delete error: {str(e)}"

# --- SCREEN UTILITIES ---

@mcp.tool()
def screen_get_pixel_color(x: int, y: int) -> str:
    """Get the RGB color of a pixel at the specified screen coordinates."""
    try:
        img = ImageGrab.grab()
        color = img.getpixel((x, y))
        hex_color = '#{:02x}{:02x}{:02x}'.format(*color[:3])
        return f"Color at ({x},{y}): RGB{color} {hex_color}"
    except Exception as e:
        return f"Color pick error: {str(e)}"

@mcp.tool()
def screen_get_region(x: int, y: int, width: int, height: int) -> list:
    """
    Capture a specific region of the screen and return as image.
    Use this when you only need to analyze a portion of the screen.
    """
    try:
        img = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        w, h = img.size
        if max(w, h) > 1280:
            scale = 1280 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=60, optimize=True)
        b64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        return [ImageContent(type="image", data=b64, mimeType="image/jpeg")]
    except Exception as e:
        raise Exception(f"Region capture error: {str(e)}")

# --- PYTHON EXECUTION ---

@mcp.tool()
async def execute_python_code(code: str, required_libs: list[str] = None, timeout: int = 120) -> str:
    """
    Execute Python code in the project environment.
    Automatically installs required libraries.
    code: Complete Python script to run
    required_libs: Pip package names to install first
    timeout: Max execution time in seconds (default 120)
    """
    output = []
    try:
        if required_libs:
            output.append(f"Installing deps: {', '.join(required_libs)}")
            proc = await asyncio.create_subprocess_exec(
                "uv", "add", *required_libs,
                cwd=WORKSPACE_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return f"Install failed:\n{stderr.decode('utf-8', errors='replace')}"
            output.append("Dependencies installed.")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            script_path = f.name

        output.append(f"Executing script...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.terminate()
            try: os.remove(script_path)
            except: pass
            return f"Script timed out after {timeout}s."

        if stdout:
            output.append("--- STDOUT ---")
            output.append(stdout.decode('utf-8', errors='replace'))
        if stderr:
            output.append("--- STDERR ---")
            output.append(stderr.decode('utf-8', errors='replace'))
        output.append(f"Exit code: {proc.returncode}")

        try: os.remove(script_path)
        except: pass
    except Exception as e:
        output.append(f"Error: {str(e)}")

    return "\n".join(output)

@mcp.tool()
async def execute_python_code_background(code: str, required_libs: list[str] = None) -> str:
    """
    Execute Python code in the background (non-blocking).
    Use for long-running scripts, servers, or monitors.
    """
    try:
        if required_libs:
            proc = await asyncio.create_subprocess_exec(
                "uv", "add", *required_libs,
                cwd=WORKSPACE_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            script_path = f.name

        async def runner(path):
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
            except:
                pass
            finally:
                try: os.remove(path)
                except: pass

        asyncio.create_task(runner(script_path))
        return "Background execution started."
    except Exception as e:
        return f"Background exec error: {str(e)}"

# --- OS COMMANDS ---

@mcp.tool()
async def run_os_command(command: str, cwd: str = None, timeout: int = 60) -> str:
    """
    Run a shell command and return its output.
    command: Shell command to execute
    cwd: Working directory (defaults to project root)
    timeout: Max execution time in seconds (default 60)
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd or WORKSPACE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.terminate()
            return f"Command timed out after {timeout}s."

        output = f"Command: {command}\nExit Code: {proc.returncode}\n"
        if stdout:
            out_text = stdout.decode('utf-8', errors='replace')
            output += f"STDOUT ({len(out_text)} chars):\n{out_text[:5000]}"
            if len(out_text) > 5000:
                output += "\n... (truncated)"
        if stderr:
            output += f"\nSTDERR:\n{stderr.decode('utf-8', errors='replace')[:2000]}"
        return output
    except Exception as e:
        return f"Command error: {str(e)}"

# --- WINDOW MANAGEMENT ---

@mcp.tool()
def window_list() -> str:
    """List all open windows with their titles."""
    try:
        titles = gw.getAllTitles()
        active = [t for t in titles if t.strip()]
        if not active:
            return "No windows found."
        output = [f"Found {len(active)} windows:"]
        for i, t in enumerate(active[:50]):
            output.append(f"  [{i}] {t}")
        if len(active) > 50:
            output.append(f"  ... and {len(active)-50} more")
        return "\n".join(output)
    except Exception as e:
        return f"Window list error: {str(e)}"

@mcp.tool()
def window_focus(title: str) -> str:
    """Bring a window to the foreground by title substring."""
    try:
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        win = windows[0]
        if win.isMinimized():
            win.restore()
        win.activate()
        return f"Focused: {win.title}"
    except Exception as e:
        return f"Window focus error: {str(e)}"

@mcp.tool()
def window_manage(action: str, title: str = None) -> str:
    """
    Manage windows.
    action: 'list', 'focus', 'maximize', 'minimize', 'restore', 'close', 'move', 'resize'
    title: Window title substring
    """
    try:
        if action == 'list':
            return window_list()
        if not title:
            return "Error: 'title' required."
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            return f"No window found matching '{title}'"
        win = windows[0]
        if action == 'focus':
            win.activate()
        elif action == 'maximize':
            win.maximize()
        elif action == 'minimize':
            win.minimize()
        elif action == 'restore':
            win.restore()
        elif action == 'close':
            win.close()
        else:
            return f"Unknown action: {action}"
        return f"{action.title()} window: {win.title}"
    except Exception as e:
        return f"Window error: {str(e)}"

# --- PROCESS MANAGEMENT ---

@mcp.tool()
def process_list(top_n: int = 20, sort_by: str = "memory") -> str:
    """
    List running processes.
    top_n: Number of processes to show (default 20)
    sort_by: 'memory' (default), 'cpu', 'name'
    """
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent', 'create_time']):
            try:
                p.info['cpu_percent'] = p.cpu_percent(interval=0.0)
                procs.append(p.info)
            except:
                pass
        if sort_by == 'memory':
            procs.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
        elif sort_by == 'cpu':
            procs.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
        elif sort_by == 'name':
            procs.sort(key=lambda x: x['name'] or '')
        output = f"Top {min(top_n, len(procs))} Processes:\n"
        for p in procs[:top_n]:
            mem = p['memory_percent'] or 0
            cpu = p['cpu_percent'] or 0
            output += f"PID:{p['pid']:>7} {mem:>5.1f}%MEM {cpu:>5.1f}%CPU {p['name'][:30]}\n"
        return output
    except Exception as e:
        return f"Process list error: {str(e)}"

@mcp.tool()
def process_kill(target: str, by: str = "pid") -> str:
    """
    Kill a process by PID or name.
    target: PID number or process name
    by: 'pid' (default) or 'name'
    """
    try:
        if by == "pid":
            p = psutil.Process(int(target))
            name = p.name()
            p.terminate()
            return f"Terminated PID {target} ({name})"
        elif by == "name":
            count = 0
            for p in psutil.process_iter(['name']):
                if target.lower() in p.info['name'].lower():
                    p.terminate()
                    count += 1
            return f"Terminated {count} processes matching '{target}'"
        return f"Invalid 'by' parameter: {by}"
    except Exception as e:
        return f"Kill error: {str(e)}"

@mcp.tool()
def process_start(command: str, cwd: str = None) -> str:
    """
    Start a new process.
    command: Command to run
    cwd: Working directory
    """
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd or WORKSPACE_DIR,
            shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return f"Started process PID {proc.pid}: {command[:100]}"
    except Exception as e:
        return f"Process start error: {str(e)}"

# --- SYSTEM INFO ---

@mcp.tool()
def system_info() -> str:
    """Get system information: CPU, memory, disk, OS, uptime."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        cpu_count = psutil.cpu_count()
        mem = psutil.virtual_memory()
        _disk_path = os.getenv("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
        disk = psutil.disk_usage(_disk_path)
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot
        return (
            f"--- System Info ---\n"
            f"OS: {os.name} | Python {sys.version.split()[0]}\n"
            f"CPU: {cpu}% ({cpu_count} cores)\n"
            f"RAM: {mem.percent}% ({mem.used//(1024**3)}GB/{mem.total//(1024**3)}GB)\n"
            f"Disk: {disk.percent}% ({disk.free//(1024**3)}GB free / {disk.total//(1024**3)}GB)\n"
            f"Uptime: {uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m\n"
            f"Screen: {_screen_size()}"
        )
    except Exception as e:
        return f"System info error: {str(e)}"

# --- MEDIA & NOTIFICATIONS ---

@mcp.tool()
def media_control(action: str) -> str:
    """
    Control system media playback.
    action: 'volume_up', 'volume_down', 'volume_mute', 'playpause', 'nexttrack', 'prevtrack', 'stop'
    """
    try:
        mapping = {
            'volume_up': 'volumeup',
            'volume_down': 'volumedown',
            'volume_mute': 'volumemute',
            'playpause': 'playpause',
            'nexttrack': 'nexttrack',
            'prevtrack': 'prevtrack',
            'stop': 'stop',
        }
        if action not in mapping:
            return f"Invalid action. Valid: {', '.join(mapping.keys())}"
        pyautogui.press(mapping[action])
        return f"Media: {action}"
    except Exception as e:
        return f"Media error: {str(e)}"

@mcp.tool()
def notify(title: str, message: str, duration: int = 5) -> str:
    """
    Show a desktop notification.
    title: Notification title
    message: Notification body
    duration: Duration in seconds (default 5)
    """
    try:
        from win10toast import ToastNotifier
        import threading
        toaster = ToastNotifier()
        threading.Thread(
            target=toaster.show_toast,
            args=(title, message),
            kwargs={'duration': duration, 'threaded': True},
            daemon=True
        ).start()
        return f"Notification sent: {title}"
    except Exception as e:
        return f"Notification error: {str(e)}"

# --- WAIT ---

@mcp.tool()
async def wait(seconds: int = 1) -> str:
    """
    Wait for a specified number of seconds.
    Use between actions to allow pages or UI to load.
    seconds: Number of seconds to wait (default 1)
    """
    await asyncio.sleep(seconds)
    return f"Waited {seconds} seconds."

# --- OPEN BROWSER (quick launch) ---

@mcp.tool()
def open_browser(url: str) -> str:
    """
    Open a URL in Chrome (preferred) or the default browser.
    Use for quick launches where you just need to open a page.
    For full control, use browser_* tools instead.
    """
    try:
        if os.name == "nt":
            chrome_paths = [
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            for path in chrome_paths:
                if os.path.isfile(path):
                    subprocess.Popen([path, url], close_fds=True)
                    return f"Opened {url} in Chrome."
            os.startfile(url)
        else:
            import webbrowser
            webbrowser.open(url)
        return f"Opened {url} in default browser."
    except Exception as e:
        return f"Failed to open browser: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
