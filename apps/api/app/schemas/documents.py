from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentType = Literal["soc_report", "bridge_letter", "internal_control_framework"]
ExtractionStatus = Literal["pending", "processing", "complete", "failed"]


class DocumentOut(BaseModel):
    id: str
    organization_id: str
    audit_period_id: str
    document_type: DocumentType
    file_name: str
    file_size_bytes: int
    content_type: str
    uploaded_by: str
    created_at: datetime
    # Short-lived signed URL, generated per-request — not stored, so it's
    # populated by the service layer rather than mapped straight off the
    # DB row the way the other fields are.
    view_url: str
    # NULL for content types this pipeline doesn't run on (e.g. XLSX/CSV) —
    # see database/migrations/0003_document_pages_extraction.sql.
    extraction_status: ExtractionStatus | None = None
    extraction_error: str | None = None
