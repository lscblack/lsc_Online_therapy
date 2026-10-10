"""PDF text extraction (pypdf). Failures raise ExtractionError; callers mark the doc failed."""
import io
from dataclasses import dataclass

from pypdf import PdfReader


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class Page:
    page_number: int  # 1-based
    text: str


def extract_text(data: bytes) -> list[Page]:
    """Return pages that contain text. Raises ExtractionError for empty, garbage,
    password-protected, or text-less (e.g. scanned) PDFs."""
    if not data:
        raise ExtractionError("empty file")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("PDF is password-protected")
        pages = []
        for i, p in enumerate(reader.pages, start=1):
            text = (p.extract_text() or "").strip()
            if text:
                pages.append(Page(i, text))
    except ExtractionError:
        raise
    except Exception as e:  # pypdf raises many types for malformed input
        raise ExtractionError(f"unreadable PDF: {type(e).__name__}") from e
    if not pages:
        raise ExtractionError("no extractable text (scanned or empty PDF)")
    return pages
