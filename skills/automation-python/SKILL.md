---
name: automation-python
description: Specialized instructions for writing robust, self-healing Python scripts for OS automation.
---

# Python Automation Skill

When using the `execute_python_code` tool, adhere to these advanced scripting principles:

## 1. Zero-Friction Dependencies
The workspace uses `uv` for dependency management. When generating a Python script, explicitly declare EVERY non-standard library your script imports in the `required_libs` parameter. 
- Example: If your script uses `import pandas as pd`, set `required_libs=["pandas"]`.

## 2. Defensive Programming
Assume the OS environment is chaotic.
- Wrap critical OS interactions or file reads in `try/except` blocks.
- Print exact reasons for failure to `sys.stderr`.

```python
import sys
import os

try:
    # Your automation logic here
    result = "Success"
    print(result)
except Exception as e:
    print(f"FATAL ERROR: {str(e)}", file=sys.stderr)
    sys.exit(1)
```

## 3. Data Extraction Format
When extracting data via Python to read back into your AI context, format the output as JSON or structured CSV. Do not output unstructured text that requires complex regex to parse.

## 4. UI Automation via Python
While you have `control_ui`, writing a full script using `pyautogui` is often better for complex, multi-step macros.
- Always use `pyautogui.sleep()` between actions to let the UI respond.
- Example:
```python
import pyautogui
import time

time.sleep(1) # wait for focus
pyautogui.click(100, 200)
time.sleep(0.5)
pyautogui.write("Automation is supreme")
```
