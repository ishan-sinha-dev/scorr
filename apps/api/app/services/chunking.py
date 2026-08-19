from dataclasses import dataclass

from app.core.config import settings
from app.schemas.document_pages import DocumentPageOut


@dataclass(frozen=True)
class Chunk:
    """A contiguous run of pages formatted as one prompt-ready string, each
    page prefixed `[Page N]` — this is what lets the extraction schema
    require a page_number citation per item: the model only ever has to
    copy a number that's already in front of it."""

    page_numbers: list[int]
    text: str


def chunk_pages(pages: list[DocumentPageOut]) -> list[Chunk]:
    """Groups consecutive pages into chunks bounded by
    settings.ai_chunk_max_chars — never send a whole report in one prompt.

    Pages with no extractable text (needs_ocr) are skipped: a free,
    deterministic pre-filter, so no separate AI classification stage is
    needed just to skip blank pages.
    """
    usable_pages = [
        page
        for page in sorted(pages, key=lambda p: p.page_number)
        if not page.needs_ocr and page.text.strip()
    ]

    chunks: list[Chunk] = []
    current_pages: list[int] = []
    current_parts: list[str] = []
    current_len = 0

    for page in usable_pages:
        formatted = f"[Page {page.page_number}]\n{page.text}"
        if current_parts and current_len + len(formatted) > settings.ai_chunk_max_chars:
            chunks.append(Chunk(page_numbers=current_pages, text="\n\n".join(current_parts)))
            current_pages, current_parts, current_len = [], [], 0
        current_pages.append(page.page_number)
        current_parts.append(formatted)
        current_len += len(formatted)

    if current_parts:
        chunks.append(Chunk(page_numbers=current_pages, text="\n\n".join(current_parts)))

    return chunks
