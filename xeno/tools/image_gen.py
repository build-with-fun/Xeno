"""Image generation tools for Xeno.

Supports multiple providers:
- pollinations: Free, no API key needed (default)
- gemini: Google Gemini image generation (requires GEMINI_API_KEY)
- openai: DALL-E (requires OPENAI_API_KEY)

Images are saved to the current project's workspace folder,
or to workspace/resources/ if no project context.
"""

import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"
RESOURCES_DIR = WORKSPACE_DIR / "resources"


def _get_output_dir(project: str = "") -> Path:
    """Get the output directory for generated images."""
    if project:
        out = WORKSPACE_DIR / project / "images"
    else:
        out = RESOURCES_DIR / "images"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _filename_from_prompt(prompt: str, ext: str = "png") -> str:
    """Generate a filename from the prompt."""
    slug = hashlib.md5(prompt.encode()).hexdigest()[:10]
    short = prompt[:40].replace(" ", "_").replace("/", "-")
    short = "".join(c for c in short if c.isalnum() or c in "_-")
    return f"{short}_{slug}.{ext}"


def _resolve_output_path(project: str, filename: str, output_path: str, ext: str) -> Path:
    """Resolve the output path from the various input options.

    Priority: output_path > project+filename > project > default
    """
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if filename:
        out_dir = _get_output_dir(project)
        return out_dir / filename

    return _get_output_dir(project)


async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    project: str = "",
    filename: str = "",
    output_path: str = "",
    provider: str = "",
    model: str = "",
    num_images: int = 1,
) -> str:
    """Generate an image from a text prompt.

    The caller controls exactly where the file goes:
    - Set output_path to a full path (e.g. 'workspace/myapp/static/img/hero.png')
      to save to an EXACT location. The coding agent should set this to put
      images in whatever folder the project needs.
    - Set filename + project to save as <name> inside workspace/<project>/images/.
    - Leave both empty to auto-generate in workspace/resources/images/.

    Args:
        prompt: Description of the image to generate.
        width: Image width in pixels (default 1024).
        height: Image height in pixels (default 1024).
        project: Project folder name inside workspace/ (e.g. 'portfolio').
        filename: Exact filename (e.g. 'hero.png', 'logo.svg').
        output_path: Full output path override (e.g. 'workspace/site/assets/img/banner.jpg').
                     Highest priority — overrides project and filename.
        provider: Image provider (pollinations, gemini, openai). Auto-detect if empty.
        model: Model name override. Provider default if empty.
        num_images: Number of images to generate (1-4).

    Returns:
        Path(s) to the generated image(s).
    """
    num_images = max(1, min(4, num_images))

    config = _load_image_config()
    if not provider:
        provider = config.get("provider", "pollinations")
    if not model:
        model = config.get("model", "")

    results = []

    for i in range(num_images):
        try:
            ext = "png"
            out_dir = _resolve_output_path(project, filename, output_path, ext)

            if output_path:
                resolved_dir = out_dir.parent
                resolved_dir.mkdir(parents=True, exist_ok=True)
                path = out_dir
            elif filename:
                resolved_dir = out_dir.parent if out_dir.suffix else out_dir
                if out_dir.suffix:
                    path = out_dir
                else:
                    resolved_dir.mkdir(parents=True, exist_ok=True)
                    path = resolved_dir / filename
            else:
                resolved_dir = out_dir
                resolved_dir.mkdir(parents=True, exist_ok=True)

            if provider == "pollinations":
                path = await _gen_pollinations(prompt, width, height, path if output_path else resolved_dir, i, filename)
            elif provider == "gemini":
                path = await _gen_gemini(prompt, width, height, path if output_path else resolved_dir, config, i, filename)
            elif provider == "openai":
                path = await _gen_openai(prompt, width, height, path if output_path else resolved_dir, config, model, i, filename)
            else:
                path = await _gen_pollinations(prompt, width, height, path if output_path else resolved_dir, i, filename)

            results.append(str(path))
            logger.info(f"Image generated: {path}")
        except Exception as e:
            logger.error(f"Image generation failed ({provider}): {e}")
            results.append(f"Error: {e}")

    if len(results) == 1:
        return results[0]
    return "\n".join(results)


async def _gen_pollinations(
    prompt: str, width: int, height: int, output_dir: Path, index: int, filename: str = ""
) -> Path:
    """Generate image using Pollinations.ai (free, no key)."""
    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    seed = int(time.time()) + index
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()

    ext = "png"
    ct = resp.headers.get("content-type", "")
    if "jpeg" in ct or "jpg" in ct:
        ext = "jpg"
    elif "webp" in ct:
        ext = "webp"

    if not filename:
        filename = _filename_from_prompt(prompt, ext)
        if index > 0:
            filename = f"{index+1}_{filename}"
    path = output_dir / filename if output_dir.suffix == "" else output_dir
    path.write_bytes(resp.content)
    return path


async def _gen_gemini(
    prompt: str, width: int, height: int, output_dir: Path, config: dict, index: int, filename: str = ""
) -> Path:
    """Generate image using Google Gemini image generation."""
    api_key = config.get("api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set. Add it to .env or setup.")

    model = config.get("model", "gemini-2.0-flash-exp")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": f"Generate an image: {prompt}. Make it high quality and detailed."}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "responseMimeType": "text/plain",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Extract image from response
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                import base64
                img_data = base64.b64decode(part["inlineData"]["data"])
                mime = part["inlineData"].get("mimeType", "image/png")
                ext = "png" if "png" in mime else "jpg" if "jpeg" in mime or "jpg" in mime else "webp"
                if not filename:
                    filename = _filename_from_prompt(prompt, ext)
                    if index > 0:
                        filename = f"{index+1}_{filename}"
                path = output_dir / filename if output_dir.suffix == "" else output_dir
                path.write_bytes(img_data)
                return path

    raise RuntimeError("No image found in Gemini response")


async def _gen_openai(
    prompt: str, width: int, height: int, output_dir: Path, config: dict, model: str, index: int, filename: str = ""
) -> Path:
    """Generate image using OpenAI DALL-E."""
    api_key = config.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to .env or setup.")

    model = model or "dall-e-3"
    url = "https://api.openai.com/v1/images/generations"

    # Map dimensions to DALL-E sizes
    if width > height:
        size = "1792x1024"
    elif height > width:
        size = "1024x1792"
    else:
        size = "1024x1024"

    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        data = resp.json()

    import base64
    for item in data.get("data", []):
        if "b64_json" in item:
            img_data = base64.b64decode(item["b64_json"])
    if not filename:
        filename = _filename_from_prompt(prompt, "png")
        if index > 0:
            filename = f"{index+1}_{filename}"
    path = output_dir / filename if output_dir.suffix == "" else output_dir
    path.write_bytes(img_data)
    return path

raise RuntimeError("No image found in OpenAI response")


def _load_image_config() -> dict:
    """Load image config from setup.json."""
    setup_file = Path(__file__).parent.parent.parent / "data" / "setup.json"
    if setup_file.exists():
        try:
            import json
            data = json.loads(setup_file.read_text())
            return {
                "provider": data.get("image_provider", "pollinations"),
                "model": data.get("image_model", ""),
                "api_key": data.get("image_api_key", ""),
            }
        except Exception:
            pass
    return {"provider": "pollinations", "model": "", "api_key": ""}
