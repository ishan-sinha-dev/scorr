from datetime import datetime

from pydantic import BaseModel, Field


class ControlMappingCandidate(BaseModel):
    """One LLM-confirmed match between the internal control being mapped
    and a soc_control from the vector-searched candidate pool. soc_control_id
    (and the two id lists below) must be an id from the candidate pool
    handed to the model in the prompt — the caller validates that before
    persisting anything, never trusting an id it didn't offer."""

    soc_control_id: str
    confidence: float = Field(ge=0, le=1)
    relevance_summary: str
    relevant_cuec_ids: list[str] = Field(default_factory=list)
    relevant_exception_ids: list[str] = Field(default_factory=list)


class ControlMappingResult(BaseModel):
    """Only genuinely relevant matches belong here — the model is
    instructed to omit candidates it doesn't confirm rather than return a
    relevant=False entry, so an empty list is a real 'nothing relevant'
    signal, not a missing field."""

    mappings: list[ControlMappingCandidate]


class ControlMappingOut(BaseModel):
    id: str
    organization_id: str
    audit_period_id: str
    internal_control_id: str
    soc_control_id: str
    similarity_score: float
    confidence: float
    relevance_summary: str
    requires_review: bool
    created_at: datetime
