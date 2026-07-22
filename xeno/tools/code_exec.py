import io
import sys
import contextlib
import traceback
from typing import Any


def execute_python(code: str, timeout: int = 60) -> str:
    """Execute Python code in a sandboxed environment and return stdout/stderr. Use for data processing, calculations, file operations, and more."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    local_vars: dict[str, Any] = {}

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, {"__builtins__": __builtins__}, local_vars)

        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        result = ""
        if stdout_val:
            result += stdout_val
        if stderr_val:
            result += f"\n[STDERR]\n{stderr_val}" if result else stderr_val

        return result.strip()[:10000] if result.strip() else "Code executed successfully (no output)"
    except Exception:
        tb = traceback.format_exc()
        return f"Error:\n{tb[:5000]}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
