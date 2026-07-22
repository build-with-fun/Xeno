"""Vision tools — screen capture, camera capture, and vision description.

Uses the configured vision model (supports any LangChain provider).
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from typing import Any

import pyautogui
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_vision_model():
    """Get a vision-capable LangChain chat model from the config."""
    from xeno.config import XenoConfig
    from langchain.chat_models import init_chat_model
    cfg = XenoConfig.from_env()
    model_str = cfg.vision_model or cfg.model
    provider = None
    model_name = model_str
    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
    # Normalize provider - Ollama uses OpenAI-compatible API
    if provider == "ollama":
        provider = "openai"
    kwargs = {}
    if provider:
        kwargs["model_provider"] = provider
    return init_chat_model(model_name, **kwargs)


def capture_screen_base64() -> str:
    """Capture the screen and return as base64 JPEG."""
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def capture_camera_base64(timeout_sec: float = 3.0) -> str:
    """Capture from the first webcam and return as base64 JPEG."""
    try:
        import cv2
    except ImportError:
        raise RuntimeError("opencv-python not installed. Run: uv pip install opencv-python")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")

    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Failed to capture from webcam")

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


async def _vision_ask(prompt: str, image_base64: str) -> str:
    """Send an image to the vision model and get a description."""
    llm = _get_vision_model()
    from langchain_core.messages import HumanMessage

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
        },
    ])
    try:
        result = await llm.ainvoke([msg])
        content = result.content
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    parts.append(c.get("text", str(c)))
                else:
                    parts.append(str(c))
            content = " ".join(parts)
        return str(content) if content else "(no description)"
    except Exception as e:
        logger.error(f"Vision LLM failed: {e}")
        return f"Vision analysis failed: {e}"


# --- Tool functions (registered in TOOL_REGISTRY) ---

@tool
async def analyze_image(image_b64: str, caption: str = "", question: str = "") -> str:
    """Analyze an image from base64-encoded data. Returns a detailed description. Use for: understanding images received via WhatsApp, documents with images, or any user-provided image. If mimetype is not jpeg, specify it (e.g. 'image/png')."""
    try:
        from langchain_core.messages import HumanMessage
        model = _get_vision_model()
        if model is None:
            return "Vision model not available"
        content = [
            {"type": "text", "text": f"Caption: {caption}\nQuestion: {question}\nAnalyze this image in detail. Describe all visible content, text, and context."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
        msg = HumanMessage(content=content)
        r = await model.ainvoke([msg])
        return r.content if hasattr(r, "content") else str(r)
    except Exception as e:
        return f"Image analysis failed: {e}"

@tool
async def describe_screen(ask: str = "") -> str:
    """Describe what's currently visible on the screen. Captures a screenshot and uses AI vision to describe it.
    ask: optional specific question about something on screen (e.g. 'what buttons are visible?', 'where is the search box?', 'read the text in the popup').
    """
    try:
        b64 = capture_screen_base64()
        if ask:
            prompt = f"The user asks: {ask}\nLook at the screenshot and answer the question. Be specific and precise."
        else:
            prompt = "Describe what you see on this screen in 2-3 sentences. Focus on visible apps, content, and overall context."
        return await _vision_ask(prompt, b64)
    except Exception as e:
        return f"Screen capture failed: {e}"


@tool
async def describe_camera() -> str:
    """Capture a photo from the webcam and describe what it shows. Use this when the user asks how they look or what's in front of the camera."""
    try:
        b64 = capture_camera_base64()
        prompt = "Describe the person or scene in this photo in 2-3 sentences. Focus on appearance, expression, lighting, and background."
        return await _vision_ask(prompt, b64)
    except Exception as e:
        return f"Camera capture failed: {e}"


@tool
async def screen_status(ask: str = "") -> str:
    """Take a quick screenshot and return a summary of what's on screen (windows, content, activity). Use this to quickly check what's on the user's screen.
    ask: optional specific question about the screen state (e.g. 'did the download finish?', 'is the popup visible?', 'what color is the button?').
    """
    try:
        b64 = capture_screen_base64()
        if ask:
            prompt = f"The user asks: {ask}\nLook at this screenshot of the user's screen and answer the question directly."
        else:
            prompt = "Briefly summarize what's happening on this screen. List visible application windows, any content being viewed, and overall context in 1-2 sentences."
        return await _vision_ask(prompt, b64)
    except Exception as e:
        return f"Screen status failed: {e}"


VISION_TOOLS = [describe_screen, describe_camera, screen_status, analyze_image]