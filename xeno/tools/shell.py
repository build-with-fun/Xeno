import subprocess
import sys
import os
import json
from typing import Any


def shell_execute(command: str, timeout: int = 300) -> str:
    """Execute a shell command and return its output. Use for running system commands, installing packages, git operations, etc. Default timeout is 300s (5 min) for long operations like npx/npm installs."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}" if output else result.stderr
        if result.returncode != 0:
            output += f"\n[EXIT CODE: {result.returncode}]"
        return output.strip()[:10000] if output.strip() else "Command executed successfully (no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def shell_run_python(code: str) -> str:
    """Run Python code in a subprocess and return the output. Use for quick Python snippets that don't need the full interpreter."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd(),
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}" if output else result.stderr
        return output.strip()[:10000] if output.strip() else "Code executed successfully (no output)"
    except subprocess.TimeoutExpired:
        return "Code execution timed out after 60 seconds"
    except Exception as e:
        return f"Error running code: {str(e)}"
