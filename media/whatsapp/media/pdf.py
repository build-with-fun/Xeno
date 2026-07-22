"""PDF text extraction with OCR fallback for scanned PDFs."""
from __future__ import annotations

import io
import logging
from typing import Optional

from media.whatsapp.ai.router import router
from media.whatsapp.config import settings
from media.whatsapp.media.downloader import media_downloader
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class PDFProcessor:
    """PDF text extraction with multi-library fallback."""

    def extract(self, page, msg_id: str, caption: str = "") -> str:
        raw = media_downloader.download(page, msg_id)
        if not raw or not raw.get("bytes"):
            return "[PDF received but could not be read]"
        data = raw["bytes"]

        text = self._extract_pdfplumber(data)
        if not text:
            text = self._extract_pypdf2(data)
        if not text:
            # Possibly a scanned PDF — try OCR
            text = self._ocr_pdf(data)

        if not text:
            return "[PDF received but no text could be extracted]"

        # Summarize if too long
        if len(text) > 8000:
            summary = router.simple_text(
                f"Summarize this PDF content concisely:\n{text[:6000]}",
                settings.gemini_max_chars,
            )
            if summary:
                text = summary

        cap = f"Caption: {caption}\n" if caption else ""
        return f"{cap}[PDF Content] {text[:4000]}"

    def _extract_pdfplumber(self, data: bytes) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except ImportError:
            return ""
        except Exception as e:
            logger.debug(f"[PDF] pdfplumber failed: {e}")
            return ""

    def _extract_pypdf2(self, data: bytes) -> str:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            return ""
        except Exception as e:
            logger.debug(f"[PDF] PyPDF2 failed: {e}")
            return ""

    def _ocr_pdf(self, data: bytes) -> str:
        """OCR a scanned PDF. Requires pdf2image + tesseract."""
        try:
            import pdf2image
            import pytesseract
            from PIL import Image
            images = pdf2image.convert_from_bytes(data, dpi=200)
            text_parts = []
            for img in images:
                text_parts.append(pytesseract.image_to_string(img))
            return "\n".join(text_parts).strip()
        except ImportError:
            logger.warning("[PDF] pdf2image/pytesseract not installed for OCR fallback")
            return ""
        except Exception as e:
            logger.warning(f"[PDF] OCR failed: {e}")
            return ""


# Singleton
pdf_processor = PDFProcessor()
