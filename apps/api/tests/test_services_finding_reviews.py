from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.schemas.finding_reviews import FindingReviewCreate
from app.services.finding_reviews import record_review

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_FINDING_ID = "finding-1"
_REVIEWER_ID = "11111111-1111-1111-1111-111111111111"


def test_record_review_persists_and_logs_audit_entry() -> None:
    fake_client = MagicMock()
    fake_row = {
        "id": "review-1",
        "finding_id": _FINDING_ID,
        "reviewer_id": _REVIEWER_ID,
        "decision": "approved",
        "override_coverage_status": None,
        "notes": None,
        "created_at": datetime.now(UTC),
    }
    with (
        patch("app.services.finding_reviews.finding_reviews_repo") as fake_repo,
        patch("app.services.finding_reviews.audit_log") as fake_audit_log,
    ):
        fake_repo.insert_review.return_value = fake_row

        result = record_review(
            fake_client,
            organization_id=_ORG_ID,
            finding_id=_FINDING_ID,
            reviewer_id=_REVIEWER_ID,
            payload=FindingReviewCreate(decision="approved"),
        )

        assert result.decision == "approved"
        fake_repo.insert_review.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            finding_id=_FINDING_ID,
            reviewer_id=_REVIEWER_ID,
            decision="approved",
            override_coverage_status=None,
            notes=None,
        )
        fake_audit_log.record.assert_called_once()
        assert fake_audit_log.record.call_args.kwargs["action"] == "finding.reviewed"
