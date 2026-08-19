from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ExtractionMethod = Literal["deterministic", "ai"]


class InternalControlExtraction(BaseModel):
    """AI-fallback structured-output target for PDF/DOCX internal control
    frameworks — mirrors the deterministic parser's ParsedControl shape,
    plus the page citation an AI extraction can (and must) provide."""

    control_id: str | None = None
    description: str
    page_number: int
    confidence: float = Field(ge=0, le=1)


class InternalControlListExtraction(BaseModel):
    controls: list[InternalControlExtraction]


class InternalControlOut(BaseModel):
    id: str
    organization_id: str
    audit_period_id: str
    document_id: str
    control_id: str | None
    description: str
    source_row_ref: str | None
    extraction_method: ExtractionMethod
    requires_review: bool
    created_at: datetime
