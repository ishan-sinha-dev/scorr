import io

import pdfplumber
from docx import Document as DocxDocument

from app.schemas.document_pages import PageExtraction

_PDF_CONTENT_TYPE = "application/pdf"
_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Content types this pipeline runs on. XLSX/CSV are deliberately excluded —
# Phase 6 parses those directly as structured rows; extracting "page text"
# from a spreadsheet has no consumer.
EXTRACTABLE_CONTENT_TYPES = frozenset({_PDF_CONTENT_TYPE, _DOCX_CONTENT_TYPE})


def extract_pdf_pages(content: bytes) -> list[PageExtraction]:
    pages: list[PageExtraction] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append(PageExtraction(page_number=index, text=text, needs_ocr=not text))
    return pages


def extract_docx_pages(content: bytes) -> list[PageExtraction]:
    # The .docx format has no fixed page boundaries — pagination is a
    # rendering-time concern, not something stored in the file. Treated as
    # one synthetic page rather than fabricating page breaks that don't
    # exist in the source (see docs/architecture/phase0-assessment.md).
    document = DocxDocument(io.BytesIO(content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    return [PageExtraction(page_number=1, text=text, needs_ocr=not text)]


def extract_pages(content_type: str, content: bytes) -> list[PageExtraction]:
    if content_type == _PDF_CONTENT_TYPE:
        return extract_pdf_pages(content)
    if content_type == _DOCX_CONTENT_TYPE:
        return extract_docx_pages(content)
    raise ValueError(f"No extractor for content type: {content_type}")
