from datetime import UTC, datetime

from app.core.config import settings
from app.schemas.document_pages import DocumentPageOut
from app.services.chunking import chunk_pages

_NOW = datetime.now(UTC)


def _page(page_number: int, text: str, needs_ocr: bool = False) -> DocumentPageOut:
    return DocumentPageOut(
        id=f"page-{page_number}",
        document_id="doc-1",
        page_number=page_number,
        text=text,
        needs_ocr=needs_ocr,
        created_at=_NOW,
    )


def test_chunk_pages_skips_needs_ocr_and_empty_pages() -> None:
    pages = [
        _page(1, "real text"),
        _page(2, "", needs_ocr=True),
        _page(3, "   ", needs_ocr=False),  # whitespace-only, no real content
        _page(4, "more text"),
    ]

    chunks = chunk_pages(pages)

    assert len(chunks) == 1
    assert chunks[0].page_numbers == [1, 4]
    assert "[Page 1]" in chunks[0].text
    assert "[Page 4]" in chunks[0].text
    assert "[Page 2]" not in chunks[0].text


def test_chunk_pages_respects_max_chars_boundary() -> None:
    original_limit = settings.ai_chunk_max_chars
    settings.ai_chunk_max_chars = 50
    try:
        pages = [_page(1, "a" * 40), _page(2, "b" * 40), _page(3, "c" * 40)]
        chunks = chunk_pages(pages)
    finally:
        settings.ai_chunk_max_chars = original_limit

    # Each page's formatted text alone exceeds nothing, but two together
    # exceed the 50-char limit, so each page lands in its own chunk.
    assert len(chunks) == 3
    assert [c.page_numbers for c in chunks] == [[1], [2], [3]]


def test_chunk_pages_orders_by_page_number_regardless_of_input_order() -> None:
    pages = [_page(3, "third"), _page(1, "first"), _page(2, "second")]

    chunks = chunk_pages(pages)

    assert chunks[0].page_numbers == [1, 2, 3]


def test_chunk_pages_empty_input_returns_no_chunks() -> None:
    assert chunk_pages([]) == []
