import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from google import genai
from PIL import Image

load_dotenv()

WORKSPACE_DIR = Path(__file__).parent.parent.parent.parent
DEFAULT_OUTPUT_DIR = WORKSPACE_DIR / "agent_output"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("Resource Generator Server")


def get_gemini_keys() -> list[str]:
    """
    Returns all configured Gemini API keys while removing duplicates.
    Supports:
        GEMINI_API_KEY
        GEMINI_API_KEY_1
        GEMINI_API_KEY_2
        ...
    """
    keys = []

    primary = os.getenv("GEMINI_API_KEY")
    if primary:
        keys.append(primary)

    for i in range(1, 100):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)

    seen = set()
    unique = []

    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)

    return unique


async def _generate_image_with_fallback(prompt: str):
    """
    Tries every configured Gemini key until one succeeds.
    Returns:
        (image_bytes, key_index)
    Raises:
        RuntimeError if all keys fail.
    """
    keys = get_gemini_keys()

    if not keys:
        raise RuntimeError("No Gemini API keys found.")

    last_error = None

    for idx, api_key in enumerate(keys, start=1):
        try:
            client = genai.Client(api_key=api_key)

            response = client.models.generate_images(
                model=os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp"),
                prompt=prompt,
                config={
                    "number_of_images": 1,
                },
            )

            if (
                hasattr(response, "generated_images")
                and response.generated_images
            ):
                return (
                    response.generated_images[0].image.image_bytes,
                    idx,
                )

            last_error = f"Key {idx}: API returned no images."

        except Exception as e:
            last_error = f"Key {idx}: {e}"

    raise RuntimeError(last_error)


@mcp.tool()
async def generate_image(
    prompt: str,
    filename: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Generates an image using Gemini Flash Image.
    Saves it to disk.
    """

    target_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        filename += ".png"

    filepath = target_dir / filename

    try:
        image_bytes, key_used = await _generate_image_with_fallback(prompt)

        image = Image.open(BytesIO(image_bytes))
        image.save(filepath)

        return (
            f"Image successfully generated and saved to:\n"
            f"{filepath.resolve()}\n"
            f"(API key #{key_used})"
        )

    except Exception as e:
        return f"Error generating image: {e}"


@mcp.tool()
async def generate_pdf_from_html(
    html_content: str,
    filename: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Converts HTML into PDF using Playwright Chromium.
    """

    target_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    filepath = target_dir / filename

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await page.set_content(
                html_content,
                wait_until="networkidle",
            )

            await page.pdf(
                path=str(filepath),
                format="A4",
                print_background=True,
                margin={
                    "top": "20px",
                    "right": "20px",
                    "bottom": "20px",
                    "left": "20px",
                },
            )

            await browser.close()

        return f"PDF successfully generated:\n{filepath.resolve()}"

    except Exception as e:
        return (
            "Error generating PDF:\n"
            f"{e}\n\n"
            "If Playwright is not installed, run:\n"
            "playwright install chromium"
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")