"""Bridge between the Xeno backend runtime and the desktop GUI.

Manages lifecycle, event subscription, and async task coordination.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class DesktopRuntimeBridge:
    """Connects the desktop GUI to the Xeno backend runtime."""

    config: Any = None
    runtime: Any = None
    brain_orchestrator: Any = None
    events_queue: Any = None
    _event_listeners: dict[str, list[Callable]] = field(default_factory=dict)
    _loop: Any = None
    _thread: Optional[threading.Thread] = None
    _running: bool = False
    _ready: bool = False
    _error: Optional[str] = None
    _profile: Any = None

    def start(self) -> bool:
        """Start the Xeno backend in a background thread with its own asyncio loop."""
        if self._ready:
            return True
        try:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._running = True
            self._thread.start()

            import time
            timeout = 30.0
            start = time.time()
            while not self._ready and time.time() - start < timeout:
                time.sleep(0.1)
            if not self._ready:
                self._error = f"Runtime failed to start within {timeout}s"
                logger.error(self._error)
                return False
            return True
        except Exception as e:
            self._error = str(e)
            logger.error(f"Runtime bridge start failed: {e}")
            return False

    def _run_loop(self):
        """Run the asyncio event loop in background thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._initialize())
        except Exception as e:
            logger.error(f"Runtime loop error: {e}")
            self._error = str(e)
        finally:
            self._loop.close()

    async def _initialize(self):
        """Initialize the Xeno runtime."""
        try:
            from xeno.config import XenoConfig
            from xeno.runtime import XenoRuntime
            from xeno.client import get_llm_client

            config = XenoConfig.from_env()

            llm = None
            try:
                llm = get_llm_client(config)
            except Exception as e:
                logger.warning(f"LLM init failed (continuing): {e}")

            runtime = XenoRuntime(config=config)
            startup_ctx = await runtime.startup(llm=llm)

            self.config = config
            self.runtime = runtime
            self.brain_orchestrator = runtime.brain_orchestrator
            self._profile = runtime.profile

            self.events_queue = runtime.brain_orchestrator.subscribe() if runtime.brain_orchestrator else None

            self._ready = True
            logger.info("Desktop runtime bridge ready")

            self._start_event_poller()
        except Exception as e:
            logger.error(f"Runtime init failed: {e}", exc_info=True)
            self._error = str(e)
            self._ready = False

    def _start_event_poller(self):
        """Start polling for brain events in the background."""

        async def poll():
            while self._running:
                try:
                    if self.events_queue is not None:
                        ev = await asyncio.wait_for(self.events_queue.get(), timeout=0.5)
                        self._dispatch("event", ev)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Event poll error: {e}")

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(poll(), self._loop)

    async def send_input(self, text: str):
        """Send user input to the brain orchestrator."""
        if self.brain_orchestrator:
            try:
                await self.brain_orchestrator.handle_user_input(text)
            except Exception as e:
                logger.error(f"Input handling error: {e}")

    def send_input_sync(self, text: str):
        """Sync wrapper for send_input."""
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.send_input(text), self._loop)
            try:
                return future.result(timeout=60)
            except Exception as e:
                logger.error(f"Sync input error: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to desktop bridge events."""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if event_type in self._event_listeners:
            self._event_listeners[event_type] = [c for c in self._event_listeners[event_type] if c != callback]

    def _dispatch(self, event_type: str, data: Any):
        for cb in self._event_listeners.get(event_type, []):
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"Event listener error: {e}")

    def get_profile(self) -> dict:
        if self._profile:
            try:
                return self._profile.full_profile()
            except Exception:
                pass
        return {}

    def set_notify_callback(self, cb: Callable):
        if self.runtime:
            self.runtime.notify_callback = cb

    def cancel_task(self):
        if self.brain_orchestrator:
            try:
                cb = asyncio.run_coroutine_threadsafe(
                    self.brain_orchestrator.cancel_running_task(), self._loop
                )
                cb.result(timeout=5)
            except Exception as e:
                logger.error(f"Cancel task error: {e}")

    def status(self) -> dict:
        if self.brain_orchestrator:
            return self.brain_orchestrator.status()
        return {}

    def stop(self):
        self._running = False
        if self.runtime:
            try:
                if self._loop and self._loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(self.runtime.shutdown(), self._loop)
                    future.result(timeout=10)
            except Exception as e:
                logger.error(f"Shutdown error: {e}")


_bridge: Optional[DesktopRuntimeBridge] = None


def get_bridge() -> DesktopRuntimeBridge:
    global _bridge
    if _bridge is None:
        _bridge = DesktopRuntimeBridge()
    return _bridge
