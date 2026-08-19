"""Extraction is pure/deterministic (no AI, no network) — tested directly
against real file bytes, no mocking needed. No fixture files are checked
in; a minimal valid PDF is hand-built here so byte offsets stay correct
without an extra PDF-writing dependency (pdfplumber itself is read-only)."""

import io

import pytest
from docx import Document as DocxDocument

from app.schemas.document_pages import PageExtraction
from app.services.extraction import (
    EXTRACTABLE_CONTENT_TYPES,
    extract_docx_pages,
    extract_pages,
    extract_pdf_pages,
)


def _build_pdf(pages_text: list[str | None]) -> bytes:
    """Hand-built minimal multi-page PDF. `None` produces a page with no
    text content at all (the needs_ocr case)."""
    objects: dict[int, bytes] = {}
    n = len(pages_text)
    font_obj = 3
    page_objs = [4 + 2 * i for i in range(n)]
    content_objs = [5 + 2 * i for i in range(n)]

    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{p} 0 R" for p in page_objs)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    objects[font_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i, text in enumerate(pages_text):
        page_obj, content_obj = page_objs[i], content_objs[i]
        objects[page_obj] = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/MediaBox [0 0 200 200] /Contents {content_obj} 0 R >>"
        ).encode()
        stream = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode() if text else b""
        objects[content_obj] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    max_obj = max(objects) + 1
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = buf.tell()
        buf.write(f"{num} 0 obj\n".encode())
        buf.write(objects[num])
        buf.write(b"\nendobj\n")
    xref_offset = buf.tell()
    buf.write(f"xref\n0 {max_obj}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for num in range(1, max_obj):
        buf.write(f"{offsets.get(num, 0):010d} 00000 n \n".encode())
    buf.write(f"trailer\n<< /Size {max_obj} /Root 1 0 R >>\n".encode())
    buf.write(f"startxref\n{xref_offset}\n%%EOF".encode())
    return buf.getvalue()


def _build_docx(paragraphs: list[str]) -> bytes:
    document = DocxDocument()
    for text in paragraphs:
        document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def test_extract_pdf_pages_finds_text_and_flags_blank_page() -> None:
    pdf_bytes = _build_pdf(["Hello World", None])

    pages = extract_pdf_pages(pdf_bytes)

    assert pages == [
        PageExtraction(page_number=1, text="Hello World", needs_ocr=False),
        PageExtraction(page_number=2, text="", needs_ocr=True),
    ]


def test_extract_docx_pages_treats_whole_document_as_one_page() -> None:
    docx_bytes = _build_docx(["First paragraph.", "Second paragraph."])

    pages = extract_docx_pages(docx_bytes)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "First paragraph." in pages[0].text
    assert "Second paragraph." in pages[0].text
    assert pages[0].needs_ocr is False


def test_extract_docx_pages_flags_empty_document() -> None:
    docx_bytes = _build_docx([])

    pages = extract_docx_pages(docx_bytes)

    assert pages == [PageExtraction(page_number=1, text="", needs_ocr=True)]


def test_extract_pages_dispatches_by_content_type() -> None:
    pdf_bytes = _build_pdf(["Only page"])

    pages = extract_pages("application/pdf", pdf_bytes)

    assert pages[0].text == "Only page"


def test_extract_pages_rejects_unsupported_content_type() -> None:
    with pytest.raises(ValueError, match="No extractor"):
        extract_pages("text/csv", b"a,b\n1,2")


def test_extractable_content_types_excludes_spreadsheets() -> None:
    assert "text/csv" not in EXTRACTABLE_CONTENT_TYPES
    assert "application/pdf" in EXTRACTABLE_CONTENT_TYPES
