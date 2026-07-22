"""Local subprocess sandbox — NO Docker."""
from __future__ import annotations
import logging, os, shutil, subprocess, sys, tempfile, time, uuid
if sys.platform != "win32":
    import resource
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
logger = logging.getLogger(__name__)

@dataclass
class SandboxConfig:
    workdir: Optional[Path] = None
    python_path: str = sys.executable
    node_path: Optional[str] = None
    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    cpu_seconds: int = 30
    file_size_limit_mb: int = 50
    allow_network: bool = True
    env: dict = field(default_factory=dict)
    persist: bool = False

@dataclass
class ExecutionResult:
    success: bool; stdout: str = ""; stderr: str = ""; exit_code: int = 0
    duration_ms: int = 0; error: str = ""; timed_out: bool = False

class LocalSandbox:
    def __init__(self, config: SandboxConfig):
        self.config = config
        if config.workdir:
            self.workdir = Path(config.workdir).resolve()
        else:
            self.workdir = Path(tempfile.mkdtemp(prefix="xeno_sb_")).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
    def _apply_limits(self):
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (self.config.cpu_seconds, self.config.cpu_seconds))
            try:
                mem = self.config.memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            except: pass
            fsize = self.config.file_size_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        except: pass
    def _build_env(self):
        env = os.environ.copy(); env.update(self.config.env)
        if not self.config.allow_network:
            env["NO_PROXY"] = "*"; env["HTTP_PROXY"] = ""; env["HTTPS_PROXY"] = ""
        return env
    def run_python(self, code, timeout=None):
        script = self.workdir / f"script_{uuid.uuid4().hex[:8]}.py"
        script.write_text(code, encoding="utf-8")
        return self._run([self.config.python_path, "-u", str(script)], timeout)
    def run_shell(self, command, timeout=None):
        if sys.platform == "win32":
            return self._run(["cmd.exe", "/c", command], timeout)
        return self._run(["bash", "-c", command], timeout)
    def _run(self, cmd, timeout=None):
        actual = timeout or self.config.timeout_seconds
        start = time.time()
        try:
            proc = subprocess.run(cmd, cwd=str(self.workdir), env=self._build_env(),
                capture_output=True, text=True, timeout=actual,
                preexec_fn=self._apply_limits if sys.platform != "win32" else None)
            return ExecutionResult(proc.returncode==0, proc.stdout, proc.stderr,
                                  proc.returncode, int((time.time()-start)*1000))
        except subprocess.TimeoutExpired as e:
            return ExecutionResult(False, "", str(e.stderr or ""), -1,
                                  int((time.time()-start)*1000), f"Timed out after {actual}s", True)
        except Exception as e:
            return ExecutionResult(False, error=str(e), duration_ms=int((time.time()-start)*1000))
    def close(self):
        if not self.config.persist:
            shutil.rmtree(self.workdir, ignore_errors=True)
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

class PersistentSandboxPool:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir; self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sandboxes = {}
    def create(self, config=None):
        sid = f"sb_{uuid.uuid4().hex[:8]}"
        cfg = config or SandboxConfig()
        cfg.workdir = self.base_dir / sid; cfg.persist = True
        self._sandboxes[sid] = LocalSandbox(cfg); return sid
    def get(self, sid): return self._sandboxes.get(sid)
    def run_python(self, sid, code, timeout=None):
        sb = self.get(sid)
        return sb.run_python(code, timeout) if sb else ExecutionResult(False, error="not found")
    def destroy(self, sid):
        sb = self._sandboxes.pop(sid, None)
        if sb: shutil.rmtree(sb.workdir, ignore_errors=True); return True
        return False
    def list_active(self): return list(self._sandboxes.keys())
    def close_all(self):
        for sid in list(self._sandboxes.keys()): self.destroy(sid)
