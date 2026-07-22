"""DOCX text extraction with zipfile fallback."""
from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

from media.whatsapp.ai.router import router
from media.whatsapp.config import settings
from media.whatsapp.media.downloader import media_downloader
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

_W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class DocxProcessor:
    """DOCX text extraction."""

    def extract(self, page, msg_id: str, caption: str = "") -> str:
        raw = media_downloader.download(page, msg_id)
        if not raw or not raw.get("bytes"):
            return "[Document received but could not be read]"
        data = raw["bytes"]

        text = self._extract_python_docx(data)
        if not text:
            text = self._extract_zipfile(data)

        if not text:
            return "[Document received but no text could be extracted]"

        if len(text) > 8000:
            summary = router.simple_text(
                f"Summarize this document content concisely:\n{text[:6000]}",
                settings.gemini_max_chars,
            )
            if summary:
                text = summary

        cap = f"Caption: {caption}\n" if caption else ""
        return f"{cap}[Document Content] {text[:4000]}"

    def _extract_python_docx(self, data: bytes) -> str:
        try:
            import media.whatsapp.media.docx as docx
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return ""
        except Exception as e:
            logger.debug(f"[DOCX] python-docx failed: {e}")
            return ""

    def _extract_zipfile(self, data: bytes) -> str:
        """Pure-stdlib fallback: parse word/document.xml from the .docx zip."""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml_content = z.read("word/document.xml")
            root = ET.fromstring(xml_content)
            texts = [t.text for t in root.findall(".//w:t", _W_NS) if t.text]
            return " ".join(texts)
        except Exception as e:
            logger.warning(f"[DOCX] zipfile fallback failed: {e}")
            return ""


# Singleton
docx_processor = DocxProcessor()
