from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

ReviewDecision = Literal["approved", "overridden", "requires_reanalysis"]
CoverageStatus = Literal["FULL", "PARTIAL", "NOT_COVERED", "NOT_APPLICABLE", "REQUIRES_REVIEW"]


class FindingReviewCreate(BaseModel):
    decision: ReviewDecision
    override_coverage_status: CoverageStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_override_status_shape(self) -> Self:
        # Mirrors the DB check constraint (finding_reviews_override_status_shape)
        # so the caller gets a clear 422 instead of a raw Postgres error.
        if self.decision == "overridden" and self.override_coverage_status is None:
            raise ValueError("override_coverage_status is required when decision is 'overridden'")
        if self.decision != "overridden" and self.override_coverage_status is not None:
            raise ValueError("override_coverage_status is only valid when decision is 'overridden'")
        return self


class FindingReviewOut(BaseModel):
    id: str
    finding_id: str
    reviewer_id: str
    decision: ReviewDecision
    override_coverage_status: CoverageStatus | None
    notes: str | None
    created_at: datetime
