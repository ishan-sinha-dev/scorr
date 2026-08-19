from supabase import Client

from app.repositories import finding_reviews as finding_reviews_repo
from app.schemas.finding_reviews import FindingReviewCreate, FindingReviewOut
from app.services import audit_log


def record_review(
    client: Client,
    *,
    organization_id: str,
    finding_id: str,
    reviewer_id: str,
    payload: FindingReviewCreate,
) -> FindingReviewOut:
    row = finding_reviews_repo.insert_review(
        client,
        organization_id=organization_id,
        finding_id=finding_id,
        reviewer_id=reviewer_id,
        decision=payload.decision,
        override_coverage_status=payload.override_coverage_status,
        notes=payload.notes,
    )
    review = FindingReviewOut.model_validate(row)
    audit_log.record(
        client,
        actor_user_id=reviewer_id,
        action="finding.reviewed",
        entity_type="finding",
        entity_id=finding_id,
        organization_id=organization_id,
        metadata={
            "decision": payload.decision,
            "override_coverage_status": payload.override_coverage_status,
        },
    )
    return review
