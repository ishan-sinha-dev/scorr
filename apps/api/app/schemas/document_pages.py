from datetime import datetime

from pydantic import BaseModel


class PageExtraction(BaseModel):
    """Pure extraction result, no DB identity yet — the worker task attaches
    document_id/organization_id when persisting via document_pages_repo."""

    page_number: int
    text: str
    needs_ocr: bool


class DocumentPageOut(BaseModel):
    id: str
    document_id: str
    page_number: int
    text: str
    needs_ocr: bool
    created_at: datetime
