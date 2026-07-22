"""PDF generation tools for Xeno."""

import time
import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"
RESOURCES_DIR = WORKSPACE_DIR / "resources"


def _get_output_dir(project: str = "") -> Path:
    if project:
        out = WORKSPACE_DIR / project / "docs"
    else:
        out = RESOURCES_DIR / "docs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _filename_from_title(title: str) -> str:
    slug = hashlib.md5(title.encode()).hexdigest()[:8]
    short = title[:40].replace(" ", "_").replace("/", "-")
    short = "".join(c for c in short if c.isalnum() or c in "_-")
    return f"{short}_{slug}.pdf"


def _safe(text: str) -> str:
    return text.encode("latin-1", errors="replace").decode("latin-1")


def create_pdf(
    title: str,
    content: str,
    project: str = "",
    author: str = "",
    font_size: int = 12,
    page_size: str = "A4",
) -> str:
    """Create a PDF from markdown-style text.

    Args:
        title: Document title.
        content: Markdown text (# headings, - bullets, paragraphs).
        project: Project folder in workspace/. Empty = workspace/resources/docs/.
        author: Optional author name.
        font_size: Base font size (default 12).
        page_size: A4, Letter, or Legal.

    Returns:
        Path to the generated PDF.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return "Error: fpdf2 not installed. Run: uv pip install fpdf2"

    output_dir = _get_output_dir(project)
    path = output_dir / _filename_from_title(title)

    sizes = {"A4": (210, 297), "Letter": (215.9, 279.4), "Legal": (215.9, 355.6)}
    pw, ph = sizes.get(page_size, sizes["A4"])

    pdf = FPDF(orientation="P", unit="mm", format=(pw, ph))
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", font_size + 8)
    pdf.cell(0, 14, _safe(title), new_x="LMARGIN", new_y="NEXT", align="C")

    # Author + date
    if author:
        pdf.set_font("Helvetica", "", font_size - 2)
        pdf.cell(0, 8, _safe(f"By {author}"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", font_size - 2)
    pdf.cell(0, 8, time.strftime("%Y-%m-%d"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)

    # Body
    pdf.set_font("Helvetica", "", font_size)

    for line in content.split("\n"):
        stripped = line.strip()

        if not stripped:
            pdf.ln(4)
            continue

        if stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", font_size + 1)
            pdf.ln(3)
            pdf.multi_cell(0, 7, _safe(stripped[4:]), new_x="LMARGIN")
            pdf.ln(2)
            pdf.set_font("Helvetica", "", font_size)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", font_size + 3)
            pdf.ln(4)
            pdf.multi_cell(0, 9, _safe(stripped[3:]), new_x="LMARGIN")
            pdf.ln(3)
            pdf.set_font("Helvetica", "", font_size)
        elif stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", font_size + 5)
            pdf.ln(5)
            pdf.multi_cell(0, 11, _safe(stripped[2:]), new_x="LMARGIN")
            pdf.ln(4)
            pdf.set_font("Helvetica", "", font_size)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.multi_cell(0, 7, _safe(f"  -  {stripped[2:]}"), new_x="LMARGIN")
        elif stripped.startswith("**") and stripped.endswith("**"):
            pdf.set_font("Helvetica", "B", font_size + 1)
            pdf.multi_cell(0, 7, _safe(stripped.strip("*")), new_x="LMARGIN")
            pdf.set_font("Helvetica", "", font_size)
        else:
            clean = stripped.replace("**", "").replace("*", "").replace("`", "")
            pdf.multi_cell(0, 7, _safe(clean), new_x="LMARGIN")

    pdf.output(str(path))
    return f"PDF created: {path.resolve()} ({path.stat().st_size} bytes)"


def create_pdf_from_html(
    html_content: str,
    output_name: str,
    project: str = "",
) -> str:
    """Create a PDF from HTML content."""
    try:
        from fpdf import FPDF
    except ImportError:
        return "Error: fpdf2 not installed. Run: uv pip install fpdf2"

    output_dir = _get_output_dir(project)
    path = output_dir / f"{output_name}.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    text = re.sub(r"<[^>]+>", "\n", html_content)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    pdf.set_font("Helvetica", size=12)
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            pdf.multi_cell(0, 7, _safe(stripped))
        else:
            pdf.ln(4)

    pdf.output(str(path))
    return f"PDF created: {path.resolve()} ({path.stat().st_size} bytes)"
