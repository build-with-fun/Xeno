from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_CDP_BRIDGE: Optional["CDPBridge"] = None


def get_cdp_bridge() -> Optional["CDPBridge"]:
    global _CDP_BRIDGE
    if _CDP_BRIDGE is None:
        _CDP_BRIDGE = CDPBridge()
    return _CDP_BRIDGE


class CDPBridge:
    """Chrome DevTools Protocol bridge for direct browser control.

    Connects to a Chrome/Chromium instance via CDP to enable:
    - DOM inspection and element location
    - Network monitoring
    - Console log access
    - Screenshot capture
    - JavaScript evaluation in page context
    - Accessibility tree reading

    This is more reliable than Playwright for certain operations
    because it communicates via the browser's native debugging protocol.
    """

    def __init__(self, port: int = 9222):
        self.port = port
        self._ws_url: Optional[str] = None
        self._connected = False
        self._browser_proc: Optional[subprocess.Popen] = None

    async def ensure_browser(self, user_data_dir: Optional[str] = None) -> bool:
        if self._connected and self._ws_url:
            return True

        chrome_paths = [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]

        for path in chrome_paths:
            if os.path.exists(path):
                chrome_exe = path
                break
        else:
            chrome_exe = "chrome"

        data_dir = user_data_dir or str(Path(tempfile.gettempdir()) / "xeno-cdp-profile")
        try:
            self._browser_proc = subprocess.Popen(
                [chrome_exe, f"--remote-debugging-port={self.port}", f"--user-data-dir={data_dir}", "--no-first-run"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(2)

            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://127.0.0.1:{self.port}/json/version")
                if resp.status_code == 200:
                    data = resp.json()
                    self._ws_url = data.get("webSocketDebuggerUrl")
                    self._connected = bool(self._ws_url)
                    logger.info(f"CDP connected on port {self.port}")
                    return self._connected
        except Exception as e:
            logger.warning(f"CDP browser start failed: {e}")
            return False
        return False

    async def get_tabs(self) -> list[dict]:
        if not self._connected:
            return []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://127.0.0.1:{self.port}/json")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"CDP get_tabs failed: {e}")
        return []

    async def get_accessibility_tree(self) -> Optional[dict]:
        if not self._ws_url:
            return None
        try:
            import json
            import websockets

            async with websockets.connect(self._ws_url) as ws:
                msg_id = 1
                await ws.send(json.dumps({"id": msg_id, "method": "Target.createTarget", "params": {"url": "about:blank"}}))
                resp = await ws.recv()
                target = json.loads(resp)
                target_id = target.get("result", {}).get("targetId")
                if not target_id:
                    return None

                msg_id += 1
                await ws.send(json.dumps({"id": msg_id, "method": "Accessibility.getFullAXTree", "params": {"targetId": target_id}}))
                resp = await ws.recv()
                return json.loads(resp).get("result", {})
        except ImportError:
            logger.warning("websockets not available for CDP")
            return None
        except Exception as e:
            logger.warning(f"CDP accessibility tree failed: {e}")
            return None

    async def navigate(self, url: str) -> bool:
        if not self._ws_url:
            return False
        try:
            import json
            import websockets

            async with websockets.connect(self._ws_url) as ws:
                msg_id = 1
                await ws.send(json.dumps({"id": msg_id, "method": "Page.enable"}))
                await ws.recv()
                msg_id += 1
                await ws.send(json.dumps({"id": msg_id, "method": "Page.navigate", "params": {"url": url}}))
                await ws.recv()
                return True
        except Exception as e:
            logger.warning(f"CDP navigate failed: {e}")
            return False

    async def screenshot(self) -> Optional[bytes]:
        if not self._ws_url:
            return None
        try:
            import json
            import websockets

            async with websockets.connect(self._ws_url) as ws:
                msg_id = 1
                await ws.send(json.dumps({"id": msg_id, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
                resp = await ws.recv()
                data = json.loads(resp)
                import base64
                return base64.b64decode(data.get("result", {}).get("data", ""))
        except Exception as e:
            logger.warning(f"CDP screenshot failed: {e}")
            return None

    async def evaluate(self, script: str) -> Any:
        if not self._ws_url:
            return None
        try:
            import json
            import websockets

            async with websockets.connect(self._ws_url) as ws:
                msg_id = 1
                await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": script}}))
                resp = await ws.recv()
                return json.loads(resp).get("result", {})
        except Exception as e:
            logger.warning(f"CDP evaluate failed: {e}")
            return None

    async def close(self):
        if self._browser_proc:
            self._browser_proc.terminate()
            try:
                self._browser_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._browser_proc.kill()
        self._connected = False
        self._ws_url = None
