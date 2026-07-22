import os
import re
import asyncio
import logging
import subprocess
import signal
import tempfile
import fnmatch
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from fastmcp import FastMCP

import psutil

try:
    import pathspec
    _PATHSPEC_AVAILABLE = True
except ImportError:
    _PATHSPEC_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coder-server")

# Initialize FastMCP server
mcp = FastMCP("Coder Agent Server")

# --- Workspace / path sandboxing ---

class WorkspaceState:
    """
    Tracks a virtual "current directory" for the server instead of mutating the
    real process cwd (which would race with concurrent async tool calls).

    If CODER_AGENT_ROOT is set, every resolved path must live inside it, and
    `set_working_directory` can't move outside it either.
    """

    def __init__(self):
        self.initial_cwd = os.path.realpath(os.getcwd())
        root_env = os.environ.get("CODER_AGENT_ROOT")
        self.allowed_root = os.path.realpath(root_env) if root_env else None
        self.cwd = self.allowed_root or self.initial_cwd


workspace = WorkspaceState()


def resolve_path(path: str) -> str:
    """Resolves `path` (relative to workspace.cwd if not absolute) and enforces
    that it stays inside workspace.allowed_root, if one is configured."""
    if not os.path.isabs(path):
        candidate = os.path.join(workspace.cwd, path)
    else:
        candidate = path
    resolved = os.path.realpath(candidate)

    if workspace.allowed_root:
        try:
            common = os.path.commonpath([resolved, workspace.allowed_root])
        except ValueError:
            common = None
        if common != workspace.allowed_root:
            raise PermissionError(
                f"Access denied: '{path}' resolves to '{resolved}', which is "
                f"outside the allowed workspace root '{workspace.allowed_root}'."
            )
    return resolved


# --- Directory traversal helpers (shared by list/grep/glob/symbol search) ---

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "target", ".tox", ".eggs",
}

_gitignore_cache: Dict[str, Any] = {}


def _should_prune_dir(name: str) -> bool:
    if name in DEFAULT_IGNORE_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def _get_gitignore_spec(root_dir: str):
    """Returns a compiled pathspec for root_dir/.gitignore, or None if the
    `pathspec` package isn't installed or there's no .gitignore."""
    if not _PATHSPEC_AVAILABLE:
        return None
    if root_dir in _gitignore_cache:
        return _gitignore_cache[root_dir]
    gitignore_path = os.path.join(root_dir, ".gitignore")
    spec = None
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                spec = pathspec.PathSpec.from_lines("gitwildmatch", f.readlines())
        except Exception:
            spec = None
    _gitignore_cache[root_dir] = spec
    return spec


def _walk_filtered(root_dir: str):
    """os.walk over root_dir, pruning common build/dependency directories and
    (if `pathspec` is available) anything matched by the repo's .gitignore."""
    spec = _get_gitignore_spec(root_dir)
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not _should_prune_dir(d)]
        if spec is not None:
            kept_dirs = []
            for d in dirs:
                rel = os.path.relpath(os.path.join(root, d), root_dir)
                if not spec.match_file(rel + "/"):
                    kept_dirs.append(d)
            dirs[:] = kept_dirs
            files = [
                f for f in files
                if not spec.match_file(os.path.relpath(os.path.join(root, f), root_dir))
            ]
        yield root, dirs, files


def _glob_search_sync(pattern: str, dir_path: str, limit: int = 1000):
    matches = []
    truncated = False
    for root, _dirnames, filenames in _walk_filtered(dir_path):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))
            if len(matches) >= limit:
                return matches, True
    return matches, truncated


# --- Safe subprocess execution (argument lists, no shell interpolation) ---

async def run_command_args(args: List[str], cwd: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd or workspace.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        return {"error": f"Executable not found: {e}", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "exit_code": process.returncode,
            "success": process.returncode == 0,
        }
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return {
            "error": f"Command timed out after {timeout} seconds. Process forcefully terminated.",
            "exit_code": None,
            "success": False,
        }


# --- Background process management ---

MAX_BACKGROUND_PROCESSES = 20
MAX_COMPLETED_HISTORY = 50


class BackgroundProcessManager:
    def __init__(self):
        self.processes: Dict[int, Dict[str, Any]] = {}
        self.completed: Dict[int, Dict[str, Any]] = {}
        self.output_dir = os.path.join(os.environ.get("XENO_DATA_DIR", os.path.join(os.getcwd(), "data")), "mcp_coder_logs")
        os.makedirs(self.output_dir, exist_ok=True)

    async def start_process(self, command: str, cwd: Optional[str] = None) -> Union[int, str]:
        if len(self.processes) >= MAX_BACKGROUND_PROCESSES:
            return (f"Error: maximum of {MAX_BACKGROUND_PROCESSES} concurrent background "
                    f"processes reached. Stop or wait for one to finish first.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = os.path.join(self.output_dir, f"proc_{timestamp}.log")

        f = open(log_file, "w")
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=f,
                stderr=f,
                preexec_fn=os.setsid if os.name != "nt" else None,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        finally:
            f.close()

        self.processes[process.pid] = {
            "pid": process.pid,
            "command": command,
            "started_at": datetime.now().isoformat(),
            "process": process,
            "output_file": log_file,
        }
        return process.pid

    def _refresh(self):
        """Moves any process that has exited from `processes` into `completed`."""
        finished = []
        for pid, data in self.processes.items():
            ret = data["process"].returncode
            if ret is None:
                try:
                    p = psutil.Process(pid)
                    if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                        ret = data["process"].returncode if data["process"].returncode is not None else 0
                    else:
                        continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    ret = -1
            finished.append((pid, ret))

        for pid, ret in finished:
            data = self.processes.pop(pid)
            data["exit_code"] = ret
            data["finished_at"] = datetime.now().isoformat()
            data.pop("process", None)
            self.completed[pid] = data
            while len(self.completed) > MAX_COMPLETED_HISTORY:
                oldest_pid = next(iter(self.completed))
                self.completed.pop(oldest_pid, None)

    async def stop_process(self, pid: int, grace_period: float = 3.0) -> bool:
        if pid not in self.processes:
            return False
        process = self.processes[pid]["process"]
        try:
            if os.name == "nt":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            self._refresh()
            return False

        waited = 0.0
        while waited < grace_period:
            await asyncio.sleep(0.1)
            waited += 0.1
            if process.returncode is not None:
                break
        else:
            try:
                if os.name == "nt":
                    os.kill(pid, signal.SIGTERM)
                else:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        self._refresh()
        return True

    def list_processes(self) -> List[Dict[str, Any]]:
        self._refresh()
        active = []
        for pid, data in self.processes.items():
            try:
                p = psutil.Process(pid)
                status = p.status() if p.is_running() else "finished"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                status = "unknown"
            active.append({
                "pid": pid,
                "command": data["command"],
                "started_at": data["started_at"],
                "status": status,
                "output_file": data["output_file"],
            })
        return active

    def list_completed(self) -> List[Dict[str, Any]]:
        self._refresh()
        return [
            {
                "pid": pid,
                "command": d["command"],
                "started_at": d["started_at"],
                "finished_at": d.get("finished_at"),
                "exit_code": d.get("exit_code"),
                "output_file": d["output_file"],
            }
            for pid, d in self.completed.items()
        ]

    def get_output(self, pid: int, tail: int = 100) -> str:
        self._refresh()
        if pid in self.processes:
            log_file = self.processes[pid]["output_file"]
        elif pid in self.completed:
            log_file = self.completed[pid]["output_file"]
        else:
            return f"Error: Process {pid} not found (never existed, or its history has been pruned)."

        if not os.path.exists(log_file):
            return "No output file found."
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-tail:])

    async def wait_for(self, pid: int, timeout: float = 30.0) -> Dict[str, Any]:
        elapsed = 0.0
        interval = 0.25
        while elapsed < timeout:
            self._refresh()
            if pid in self.completed:
                d = self.completed[pid]
                return {"finished": True, "exit_code": d.get("exit_code"), "output": self.get_output(pid)}
            if pid not in self.processes:
                return {"finished": False, "error": f"Process {pid} not found."}
            await asyncio.sleep(interval)
            elapsed += interval
        return {"finished": False, "error": f"Timed out waiting for process {pid} after {timeout}s."}


proc_manager = BackgroundProcessManager()

# --- Shell execution tools ---

@mcp.tool
async def run_shell_command(command: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Executes a shell command synchronously in the current virtual working
    directory and returns stdout, stderr, and exit code.

    NOTE: this grants full shell access scoped to the workspace cwd -- it is
    not sandboxed at the OS level. Treat it as a trusted, agent-only tool.

    Args:
        command: The shell command to execute.
        timeout: Maximum time in seconds to wait for the command to finish.
    """
    logger.info(f"run_shell_command: {command!r} (cwd={workspace.cwd})")
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=workspace.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": process.returncode,
                "success": process.returncode == 0,
            }
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {
                "error": f"Command timed out after {timeout} seconds. Process forcefully terminated.",
                "exit_code": None,
                "success": False,
            }
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool
async def run_background_command(command: str) -> Dict[str, Any]:
    """
    Starts a shell command in the background (in the current virtual working
    directory) and returns a PID. Use list_background_tasks / list_completed_tasks
    to see status, get_background_task_output for logs, and
    wait_for_background_task to block until it finishes.
    """
    logger.info(f"run_background_command: {command!r} (cwd={workspace.cwd})")
    result = await proc_manager.start_process(command, cwd=workspace.cwd)
    if isinstance(result, str):
        return {"error": result, "success": False}
    return {"pid": result, "message": f"Started background process with PID {result}", "success": True}


@mcp.tool
def list_background_tasks() -> List[Dict[str, Any]]:
    """Lists all currently active background tasks started by the agent."""
    return proc_manager.list_processes()


@mcp.tool
def list_completed_tasks() -> List[Dict[str, Any]]:
    """Lists recently completed background tasks (up to the last 50) with their exit codes."""
    return proc_manager.list_completed()


@mcp.tool
async def stop_background_task(pid: int) -> Dict[str, Any]:
    """Stops a running background task by PID. Sends SIGTERM, then escalates to
    SIGKILL if the process hasn't exited within a few seconds."""
    success = await proc_manager.stop_process(pid)
    return {"success": success, "message": "Process stopped" if success else "Process not found"}


@mcp.tool
def get_background_task_output(pid: int, lines: int = 100) -> str:
    """Retrieves the last N lines of output from a background task, active or completed."""
    return proc_manager.get_output(pid, lines)


@mcp.tool
async def wait_for_background_task(pid: int, timeout: float = 30.0) -> Dict[str, Any]:
    """Blocks until a background task finishes or the timeout elapses, then returns
    its exit code and output."""
    return await proc_manager.wait_for(pid, timeout)


@mcp.tool
def cleanup_background_logs(older_than_hours: float = 24.0) -> Dict[str, Any]:
    """Deletes background-task log files older than the given age (in hours) that
    are no longer associated with a tracked active or completed process."""
    removed = []
    cutoff = datetime.now().timestamp() - older_than_hours * 3600
    tracked_files = {d["output_file"] for d in proc_manager.processes.values()}
    tracked_files |= {d["output_file"] for d in proc_manager.completed.values()}
    if os.path.isdir(proc_manager.output_dir):
        for name in os.listdir(proc_manager.output_dir):
            path = os.path.join(proc_manager.output_dir, name)
            if path in tracked_files:
                continue
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed.append(path)
            except OSError:
                continue
    return {"removed": removed, "count": len(removed)}


# --- File automation tools ---

DEFAULT_MAX_READ_BYTES = 10 * 1024 * 1024  # 10 MB


@mcp.tool
def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None,
               max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    """Reads a file and returns its content. Optional 1-indexed [start_line, end_line]
    range. Refuses to load whole files larger than max_bytes unless a line range
    is given (to avoid pulling huge files fully into memory)."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"

    if not os.path.exists(resolved):
        return f"Error: File '{file_path}' not found."
    if os.path.isdir(resolved):
        return f"Error: '{file_path}' is a directory, not a file."

    size = os.path.getsize(resolved)
    if start_line is None and end_line is None and size > max_bytes:
        return (f"Error: File is {size} bytes, which exceeds max_bytes={max_bytes}. "
                f"Specify start_line/end_line to read a portion, or pass a larger max_bytes.")

    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        if start_line is None and end_line is None:
            return f.read()
        start = (start_line - 1) if start_line and start_line > 0 else 0
        end = end_line if end_line else None
        out_lines = []
        for i, line in enumerate(f):
            if i < start:
                continue
            if end is not None and i >= end:
                break
            out_lines.append(line)
        return "".join(out_lines)


@mcp.tool
def write_file(file_path: str, content: str) -> str:
    """Writes content to a file, creating parent directories if necessary."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"write_file: wrote {len(content)} chars to {resolved}")
    return f"Successfully wrote to {file_path}"

@mcp.tool
async def write_and_test_code(file_path: str, content: str, test_runner: str = "pytest") -> Dict[str, Any]:
    """Writes content to a file, then automatically runs a linter (ruff) and tests (pytest).
    If it fails, it returns the error so the agent can self-heal before proceeding."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}
        
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
        
    logger.info(f"write_and_test_code: wrote {len(content)} chars to {resolved}")
    
    # Run Ruff (syntax/lint)
    lint_res = await run_command_args(["uv", "run", "ruff", "check", resolved], timeout=30)
    if lint_res.get("exit_code") != 0 and lint_res.get("exit_code") is not None:
        return {
            "success": False,
            "message": "Linting failed. Please fix syntax errors and rewrite.",
            "lint_output": lint_res.get("stdout", "") + "\n" + lint_res.get("stderr", "")
        }
        
    # Run Tests
    test_res = await run_command_args(["uv", "run", test_runner], timeout=60)
    if test_res.get("exit_code") != 0 and test_res.get("exit_code") is not None:
        return {
            "success": False,
            "message": "Tests failed. Please review error output and fix.",
            "test_output": test_res.get("stdout", "") + "\n" + test_res.get("stderr", "")
        }
        
    return {
        "success": True, 
        "message": f"Successfully wrote {file_path}. Linting and tests passed perfectly."
    }



@mcp.tool
def replace_text(file_path: str, old_string: str, new_string: str, expect_unique: bool = True) -> str:
    """Replaces occurrences of old_string with new_string in a file. By default
    requires old_string to be unique in the file, to avoid an unintended
    replacement at the wrong location; pass expect_unique=False to replace all
    occurrences."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(resolved):
        return f"Error: File '{file_path}' not found."

    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    count = content.count(old_string)
    if count == 0:
        return "Error: String not found in file."
    if expect_unique and count > 1:
        return (f"Error: String occurs {count} times in the file; refusing to guess which one. "
                f"Pass expect_unique=False to replace all occurrences, or include more "
                f"surrounding context in old_string to make it unique.")

    new_content = content.replace(old_string, new_string)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(new_content)
    logger.info(f"replace_text: {count} replacement(s) in {resolved}")
    return f"Successfully replaced {count} occurrence(s) in {file_path}"


MAX_LIST_RESULTS = 2000


@mcp.tool
async def list_directory(dir_path: str = ".", recursive: bool = False, timeout: int = 30) -> Dict[str, Any]:
    """Lists files and directories in a given path. When recursive=True, skips
    common build/dependency directories (.git, node_modules, venv, etc.) and
    honors .gitignore if the `pathspec` package is installed."""
    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}
    if not os.path.exists(resolved):
        return {"error": f"Directory '{dir_path}' not found.", "success": False}

    def _sync_list():
        results = []
        truncated = False
        if recursive:
            for root, dirs, files in _walk_filtered(resolved):
                for name in dirs:
                    results.append(os.path.join(root, name))
                for name in files:
                    results.append(os.path.join(root, name))
                if len(results) >= MAX_LIST_RESULTS:
                    truncated = True
                    break
        else:
            for entry in os.scandir(resolved):
                results.append(entry.path)
        return results, truncated

    try:
        items, truncated = await asyncio.wait_for(asyncio.to_thread(_sync_list), timeout=timeout)
        return {"items": items, "count": len(items), "truncated": truncated, "success": True}
    except asyncio.TimeoutError:
        return {"error": f"Directory listing timed out after {timeout} seconds.", "success": False}


@mcp.tool
async def glob_search(pattern: str, dir_path: str = ".", timeout: int = 30) -> Dict[str, Any]:
    """Finds files whose name matches a glob-style pattern (e.g. '*.py'). Skips
    common build/dependency directories."""
    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}
    if not os.path.exists(resolved):
        return {"error": f"Directory '{dir_path}' not found.", "success": False}

    try:
        matches, truncated = await asyncio.wait_for(
            asyncio.to_thread(_glob_search_sync, pattern, resolved), timeout=timeout
        )
        return {"matches": matches, "count": len(matches), "truncated": truncated, "success": True}
    except asyncio.TimeoutError:
        return {"error": f"Glob search timed out after {timeout} seconds.", "success": False}


MAX_GREP_RESULTS = 200


@mcp.tool
async def grep_search(pattern: str, dir_path: str = ".", include_pattern: str = "*", timeout: int = 60) -> Dict[str, Any]:
    """Searches for a regex pattern within file contents. Skips binary files and
    common build/dependency directories."""
    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}
    if not os.path.exists(resolved):
        return {"error": f"Directory '{dir_path}' not found.", "success": False}

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error": f"Invalid regex: {e}", "success": False}

    def _is_probably_binary(path: str) -> bool:
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
            return b"\x00" in chunk
        except Exception:
            return True

    def _sync_grep():
        results = []
        for root, _dirnames, filenames in _walk_filtered(resolved):
            for filename in fnmatch.filter(filenames, include_pattern):
                file_path = os.path.join(root, filename)
                if _is_probably_binary(file_path):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append({"file": file_path, "line": i, "content": line.strip()})
                                if len(results) >= MAX_GREP_RESULTS:
                                    return results, True
                except Exception as e:
                    logger.debug(f"grep_search: skipping {file_path}: {e}")
                    continue
        return results, False

    try:
        matches, truncated = await asyncio.wait_for(asyncio.to_thread(_sync_grep), timeout=timeout)
        return {"matches": matches, "count": len(matches), "truncated": truncated, "success": True}
    except asyncio.TimeoutError:
        return {"error": f"Grep search timed out after {timeout} seconds.", "success": False}


@mcp.tool
def file_stats(file_path: str) -> Dict[str, Any]:
    """Returns metadata about a file or directory."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return {"error": str(e)}
    if not os.path.exists(resolved):
        return {"error": "File not found"}

    stat = os.stat(resolved)
    return {
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "is_file": os.path.isfile(resolved),
        "is_dir": os.path.isdir(resolved),
    }


@mcp.tool
def delete_file(file_path: str, confirm: bool = False) -> str:
    """Deletes a file or directory. Requires confirm=True -- directory deletion
    is recursive and irreversible, so this is opt-in rather than automatic."""
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(resolved):
        return "File not found."

    is_dir = os.path.isdir(resolved)
    if not confirm:
        kind = "directory (recursively)" if is_dir else "file"
        return (f"Refusing to delete {kind} '{file_path}' without confirmation. "
                f"Call again with confirm=True to proceed.")

    if is_dir:
        import shutil
        shutil.rmtree(resolved)
        logger.warning(f"delete_file: removed directory tree {resolved}")
    else:
        os.remove(resolved)
        logger.info(f"delete_file: removed file {resolved}")
    return f"Successfully deleted {file_path}"


@mcp.tool
def make_directory(dir_path: str) -> str:
    """Creates a new directory, including parent directories if they don't exist."""
    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return f"Error: {e}"
    os.makedirs(resolved, exist_ok=True)
    return f"Successfully created directory: {dir_path}"


@mcp.tool
def move_file(source: str, destination: str, overwrite: bool = False) -> str:
    """Moves or renames a file or directory. Refuses to overwrite an existing
    destination unless overwrite=True."""
    import shutil
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(src):
        return f"Error: Source '{source}' not found."
    if os.path.exists(dst):
        if not overwrite:
            return f"Error: Destination '{destination}' already exists. Pass overwrite=True to replace it."
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)
    shutil.move(src, dst)
    logger.info(f"move_file: {src} -> {dst}")
    return f"Successfully moved {source} to {destination}"


@mcp.tool
def copy_file(source: str, destination: str, overwrite: bool = False) -> str:
    """Copies a file or directory. Refuses to overwrite an existing destination
    unless overwrite=True."""
    import shutil
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(src):
        return f"Error: Source '{source}' not found."
    if os.path.exists(dst):
        if not overwrite:
            return f"Error: Destination '{destination}' already exists. Pass overwrite=True to replace it."
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    logger.info(f"copy_file: {src} -> {dst}")
    return f"Successfully copied {source} to {destination}"


# --- Testing & quality ---

@mcp.tool
async def run_tests(test_path: Optional[str] = None, runner: str = "pytest", timeout: int = 60) -> Dict[str, Any]:
    """Runs tests using the specified runner (e.g. 'pytest', 'npm test')."""
    args = runner.split()
    if test_path:
        try:
            resolved = resolve_path(test_path)
        except PermissionError as e:
            return {"error": str(e), "success": False}
        args.append(resolved)
    return await run_command_args(args, timeout=timeout)


ALLOWED_LINTER_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]+$")


@mcp.tool
async def run_linter(file_path: str, linter: str = "ruff", timeout: int = 30) -> Dict[str, Any]:
    """Runs a linter or formatter executable (ruff, eslint, black, etc.) on a file."""
    if not ALLOWED_LINTER_PATTERN.match(linter):
        return {"error": "Invalid linter name.", "success": False}
    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}
    return await run_command_args([linter, resolved], timeout=timeout)


# --- Dependency management ---

PACKAGE_SPEC_PATTERN = re.compile(r"^[A-Za-z0-9_.\-\[\]<>=!~,+ ]+$")
ALLOWED_MANAGERS = {"pip", "pip3", "npm", "yarn", "pnpm", "uv", "cargo", "gem"}


@mcp.tool
async def manage_dependencies(action: str, package: str, manager: str = "pip", timeout: int = 300) -> Dict[str, Any]:
    """
    Installs or uninstalls a package using a package manager.

    Args:
        action: 'install' or 'uninstall'.
        package: Name (and optional version spec) of the package.
        manager: one of pip, pip3, npm, yarn, pnpm, uv, cargo, gem.
        timeout: Timeout in seconds (default 300s / 5m).
    """
    if action not in {"install", "uninstall"}:
        return {"error": "action must be 'install' or 'uninstall'.", "success": False}
    if manager not in ALLOWED_MANAGERS:
        return {"error": f"Unsupported manager '{manager}'. Allowed: {sorted(ALLOWED_MANAGERS)}", "success": False}
    if not PACKAGE_SPEC_PATTERN.match(package):
        return {"error": "Package spec contains disallowed characters.", "success": False}

    if manager in ("pip", "pip3"):
        args = [manager, action, package, "--quiet"]
    elif manager == "npm":
        args = ["npm", action, package, "--silent"]
    else:
        args = [manager, action, package]

    result = await run_command_args(args, timeout=timeout)
    logger.info(f"manage_dependencies: {manager} {action} {package} -> success={result.get('success')}")
    return result


# --- Advanced automation ---

@mcp.tool
async def analyze_project_structure(dir_path: str = ".", timeout: int = 30) -> Dict[str, Any]:
    """Provides a high-level overview of the project structure and key files,
    skipping common build/dependency directories."""
    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}

    def _sync_analyze():
        try:
            root_entries = os.listdir(resolved)
        except OSError as e:
            return {"error": str(e)}
        summary = {
            "root_files": root_entries,
            "directories": [
                d for d in root_entries
                if os.path.isdir(os.path.join(resolved, d)) and not d.startswith(".")
            ],
            "total_files": 0,
            "truncated": False,
        }
        for _root, _dirs, files in _walk_filtered(resolved):
            summary["total_files"] += len(files)
            if summary["total_files"] > 5000:
                summary["truncated"] = True
                break
        return summary

    try:
        return await asyncio.wait_for(asyncio.to_thread(_sync_analyze), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"Project analysis timed out after {timeout} seconds."}


# --- Git integration ---

@mcp.tool
async def git_status() -> str:
    """Returns the current status of the git repository."""
    result = await run_command_args(["git", "status"])
    return result.get("stdout") or result.get("stderr") or result.get("error", "Error running git status")


@mcp.tool
async def git_diff(staged: bool = False) -> str:
    """Returns the git diff. Set staged=True to see staged changes."""
    args = ["git", "diff", "--staged"] if staged else ["git", "diff"]
    result = await run_command_args(args)
    return result.get("stdout") or result.get("stderr") or result.get("error", "No changes or error")


@mcp.tool
async def git_add(file_paths: List[str]) -> str:
    """Stages specific files for commit."""
    try:
        resolved_paths = [resolve_path(p) for p in file_paths]
    except PermissionError as e:
        return f"Error: {e}"
    result = await run_command_args(["git", "add", *resolved_paths])
    if result.get("success"):
        logger.info(f"git_add: staged {file_paths}")
        return "Files staged successfully"
    return f"Error: {result.get('stderr') or result.get('error')}"


@mcp.tool
async def git_commit(message: str) -> str:
    """Commits staged changes with a message."""
    result = await run_command_args(["git", "commit", "-m", message])
    if result.get("success"):
        logger.info(f"git_commit: {message!r}")
    return result.get("stdout") or result.get("stderr") or result.get("error", "Error committing")


@mcp.tool
async def git_log(limit: int = 20) -> str:
    """Returns recent commit history in oneline format."""
    result = await run_command_args(["git", "log", f"-{limit}", "--oneline"])
    return result.get("stdout") or result.get("stderr") or result.get("error", "Error running git log")


@mcp.tool
async def git_branch_list() -> str:
    """Lists local git branches."""
    result = await run_command_args(["git", "branch"])
    return result.get("stdout") or result.get("stderr") or result.get("error", "Error listing branches")


# --- Environment & project context ---

@mcp.tool
async def get_environment_info() -> Dict[str, Any]:
    """Returns information about the current development environment."""
    import sys
    import platform

    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "python_version": sys.version,
        "working_directory": workspace.cwd,
        "workspace_root": workspace.allowed_root,
        "user": os.getenv("USERNAME") or os.getenv("USER"),
        "cpu_count": psutil.cpu_count(),
        "memory_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
    }


@mcp.tool
async def list_installed_packages() -> str:
    """Lists installed Python packages in the current environment."""
    result = await run_command_args(["pip", "list"])
    return result.get("stdout") or result.get("stderr") or result.get("error", "Error listing packages")


# --- Directory management ---

@mcp.tool
def set_working_directory(dir_path: str) -> str:
    """
    Changes the virtual working directory used to resolve relative paths and as
    the cwd for shell/git commands. This does not call os.chdir, so it's safe
    under concurrent requests; it also respects CODER_AGENT_ROOT if set.
    """
    if not os.path.isabs(dir_path):
        candidate = os.path.join(workspace.cwd, dir_path)
    else:
        candidate = dir_path
    candidate = os.path.realpath(candidate)

    if workspace.allowed_root:
        try:
            common = os.path.commonpath([candidate, workspace.allowed_root])
        except ValueError:
            common = None
        if common != workspace.allowed_root:
            return f"Error: '{dir_path}' is outside the allowed workspace root '{workspace.allowed_root}'."

    if not os.path.exists(candidate):
        return f"Error: Directory '{dir_path}' does not exist."
    if not os.path.isdir(candidate):
        return f"Error: '{dir_path}' is not a directory."

    workspace.cwd = candidate
    return f"Working directory set to: {workspace.cwd}"


@mcp.tool
def reset_to_default_directory() -> str:
    """Resets the virtual working directory to the workspace root (CODER_AGENT_ROOT),
    or to the directory the server started in if no root is configured."""
    workspace.cwd = workspace.allowed_root or workspace.initial_cwd
    return f"Working directory reset to: {workspace.cwd}"


# --- Advanced file operations ---

@mcp.tool
async def multi_file_search_replace(pattern: str, replacement: str, include: str = "*",
                                     dir_path: str = ".", dry_run: bool = False, timeout: int = 60) -> Dict[str, Any]:
    """
    Performs a search-and-replace across multiple files matching a glob pattern.

    Args:
        pattern: The string to search for.
        replacement: The string to replace it with.
        include: Glob pattern for files to include (e.g. '*.py').
        dir_path: Directory to search in.
        dry_run: If True, reports which files would be affected without writing changes.
    """
    try:
        resolved_dir = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}

    def _sync_replace():
        files, truncated = _glob_search_sync(include, resolved_dir)
        affected = []
        for file_path in files:
            if os.path.isdir(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue
            if pattern not in content:
                continue
            affected.append(file_path)
            if not dry_run:
                new_content = content.replace(pattern, replacement)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        return affected, truncated

    try:
        affected_files, truncated = await asyncio.wait_for(asyncio.to_thread(_sync_replace), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"Search/replace timed out after {timeout} seconds.", "success": False}

    if not dry_run and affected_files:
        logger.info(f"multi_file_search_replace: modified {len(affected_files)} file(s) matching '{include}'")

    return {
        "affected_files": affected_files,
        "count": len(affected_files),
        "truncated": truncated,
        "dry_run": dry_run,
        "success": True,
    }


MAX_SYMBOL_RESULTS = 300


@mcp.tool
async def search_symbols(query: str, dir_path: str = ".", timeout: int = 60) -> Dict[str, Any]:
    """Searches for classes and functions in Python files whose name contains the
    query (case-insensitive)."""
    import ast

    try:
        resolved = resolve_path(dir_path)
    except PermissionError as e:
        return {"error": str(e), "success": False}

    def _sync_search():
        results = []
        for root, _dirs, filenames in _walk_filtered(resolved):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        tree = ast.parse(f.read(), filename=file_path)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if query.lower() in node.name.lower():
                                results.append({
                                    "file": file_path,
                                    "name": node.name,
                                    "type": type(node).__name__,
                                    "line": node.lineno,
                                })
                                if len(results) >= MAX_SYMBOL_RESULTS:
                                    return results, True
                except (SyntaxError, UnicodeDecodeError):
                    continue
                except Exception as e:
                    logger.debug(f"search_symbols: skipping {file_path}: {e}")
                    continue
        return results, False

    try:
        results, truncated = await asyncio.wait_for(asyncio.to_thread(_sync_search), timeout=timeout)
        return {"matches": results, "count": len(results), "truncated": truncated, "success": True}
    except asyncio.TimeoutError:
        return {"error": f"Symbol search timed out after {timeout} seconds.", "success": False}


@mcp.tool
async def apply_diff(file_path: str, diff_content: str) -> str:
    """
    Applies a unified diff to a file using the system 'patch' utility.

    Args:
        file_path: The path to the file to patch.
        diff_content: The content of the diff (patch) to apply.
    """
    import shutil

    try:
        resolved = resolve_path(file_path)
    except PermissionError as e:
        return f"Error: {e}"
    if not os.path.exists(resolved):
        return f"Error: File '{file_path}' not found."
    if shutil.which("patch") is None:
        return "Error: the 'patch' command-line utility is not available on this system."

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tmp:
        tmp.write(diff_content)
        tmp_path = tmp.name

    try:
        result = await run_command_args(["patch", resolved, tmp_path])
        if result.get("success"):
            logger.info(f"apply_diff: patched {resolved}")
            return f"Successfully applied diff to {file_path}"
        return f"Error applying diff: {result.get('stderr') or result.get('stdout') or result.get('error')}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- JavaScript & Framework Project Scaffolding ---

@mcp.tool
async def scaffold_js_project(framework: str, project_name: str, use_ts: bool = True, timeout: int = 70) -> Dict[str, Any]:
    """
    Scaffolds a new JavaScript/TypeScript project using the latest non-interactive commands.
    
    CRITICAL: This tool executes in the CURRENT DIRECTORY (workspace.cwd).
    If you need to create the project in a specific location, you MUST either:
    1. Pass a specific directory name as `project_name` (e.g. 'my-app'), or
    2. Call `make_directory` and `set_working_directory` FIRST, and then pass "." as the `project_name`.
    
    Args:
        framework: One of 'nextjs', 'react', 'react-native', 'vue', 'svelte', 'astro', 'remix', 'angular', 'solid', 'qwik'.
        project_name: The name of the folder to create (or "." for the current directory).
        use_ts: Whether to use the TypeScript template (defaults to True).
        timeout: Maximum execution time in seconds.
    """
    try:
        target_path = resolve_path(project_name)
        os.makedirs(target_path, exist_ok=True)
    except PermissionError as e:
        return {"error": str(e), "success": False}
    except OSError as e:
        return {"error": f"Failed to create directory {target_path}: {e}", "success": False}
        
    logger.info(f"scaffold_js_project: {framework} -> {target_path} (cwd={workspace.cwd})")
    
    commands = {
        "nextjs": f"npx --yes create-next-app@latest . {'--typescript' if use_ts else '--javascript'} --tailwind --eslint --app --yes",
        "react": f"npx --yes create-vite@latest . --template {'react-ts' if use_ts else 'react'} --yes",
        "react-native": f"npx --yes create-expo-app@latest . --template blank --yes",
        "vue": f"npx --yes create-vue@latest . {'--ts' if use_ts else '--default'}",
        "svelte": f"npx --yes sv@latest create . --template minimal --types {'ts' if use_ts else 'jsdoc'} --no-add-ons --no-install",
        "astro": f"npx --yes create-astro@latest . --template minimal --yes",
        "remix": f"npx --yes create-remix@latest . --yes",
        "angular": f"npx --yes @angular/cli new my-app --directory . --defaults --skip-git --routing --style=scss --standalone",
        "solid": f"npx --yes create-vite@latest . --template {'solid-ts' if use_ts else 'solid'} --yes",
        "qwik": f"npx --yes create-vite@latest . --template {'qwik-ts' if use_ts else 'qwik'} --yes",
    }
    
    fw_lower = framework.lower()
    if fw_lower not in commands:
        return {"error": f"Unsupported framework '{framework}'. Supported: {list(commands.keys())}", "success": False}
        
    command = commands[fw_lower]
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=target_path,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            
            # Note: Many JS package managers write regular logs to stderr, so we don't automatically
            # fail if stderr has content, as long as returncode is 0.
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": process.returncode,
                "success": process.returncode == 0,
                "message": f"Successfully scaffolded {framework} project in {target_path}" if process.returncode == 0 else f"Failed to scaffold project"
            }
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return {
                "error": f"Project scaffolding timed out after {timeout} seconds.",
                "exit_code": None,
                "success": False,
            }
    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.resource("project://config")
def get_project_config() -> str:
    """Returns the content of pyproject.toml if it exists in the current working directory."""
    path = os.path.join(workspace.cwd, "pyproject.toml")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return "No pyproject.toml found"


@mcp.resource("project://readme")
def get_project_readme() -> str:
    """Returns the content of README.md if it exists in the current working directory."""
    path = os.path.join(workspace.cwd, "README.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return "No README.md found"


if __name__ == "__main__":
    mcp.run(transport="stdio")