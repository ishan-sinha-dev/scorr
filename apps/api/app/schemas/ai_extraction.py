from pydantic import BaseModel, Field


class ControlExtraction(BaseModel):
    page_number: int
    control_code: str | None = None
    description: str
    excerpt: str
    confidence: float = Field(ge=0, le=1)


class CUECExtraction(BaseModel):
    page_number: int
    description: str
    related_control_code: str | None = None
    excerpt: str
    confidence: float = Field(ge=0, le=1)


class ExceptionExtraction(BaseModel):
    page_number: int
    description: str
    related_control_code: str | None = None
    excerpt: str
    confidence: float = Field(ge=0, le=1)


class SubserviceExtraction(BaseModel):
    page_number: int
    name: str
    description: str | None = None
    excerpt: str
    confidence: float = Field(ge=0, le=1)


class ReportExtractionResult(BaseModel):
    """Structured-output target for one chunk of report text.

    All 4 categories come back from a single call rather than 4 separate
    ones — they're extracted from the same text and don't depend on each
    other, so batching them is strictly cheaper (per the spec's "batch
    independent operations" cost rule) without losing anything.
    """

    controls: list[ControlExtraction]
    cuecs: list[CUECExtraction]
    exceptions: list[ExceptionExtraction]
    subservice_organizations: list[SubserviceExtraction]
