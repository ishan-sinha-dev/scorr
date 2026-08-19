from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.finding_reviews import FindingReviewOut

CoverageStatus = Literal["FULL", "PARTIAL", "NOT_COVERED", "NOT_APPLICABLE", "REQUIRES_REVIEW"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


EvidenceKind = Literal["soc_control", "cuec", "exception"]


class EvidenceRef(BaseModel):
    """One document+page citation backing a finding — assembled at read
    time from soc_controls/cuecs/exceptions, never a separate stored copy
    (see database/migrations/0007_findings.sql). `kind` makes the
    relationship chain explicit (Phase 13: internal control -> SOC control
    -> CUEC/exception) for the UI to render as a structured chain rather
    than a flat list — no graph-visualization library added for this;
    the relationship is only ever one hop deep per evidence item, which a
    labeled list already represents clearly."""

    kind: EvidenceKind
    document_id: str
    file_name: str
    page_number: int
    excerpt: str
    view_url: str


class FindingOut(BaseModel):
    id: str
    internal_control_id: str
    internal_control_code: str | None
    internal_control_description: str
    coverage_status: CoverageStatus
    confidence: float
    reasoning: str
    created_at: datetime
    evidence: list[EvidenceRef]
    # Phase 9 (human review): coverage_status above is always the AI's own
    # derivation, never overwritten. effective_coverage_status is what the
    # UI should actually show — the latest reviewer override if one
    # exists, otherwise the same as coverage_status. latest_review is None
    # until a reviewer has acted on this finding at all.
    effective_coverage_status: CoverageStatus
    latest_review: FindingReviewOut | None = None
    # Phase 11 (risk engine): risk_level is the AI-coverage-derived risk,
    # stored alongside coverage_status. effective_risk_level is the same
    # deterministic formula re-applied to effective_coverage_status at
    # read time (never stored) — a reviewer override changes risk the same
    # way it changes coverage, without a second column to keep in sync.
    risk_level: RiskLevel
    effective_risk_level: RiskLevel
