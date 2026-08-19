from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.schemas.ai_extraction import ReportExtractionResult
from app.services.report_extraction import run_extraction_for_document

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD_ID = "33333333-3333-3333-3333-333333333333"
_DOC_ID = "44444444-4444-4444-4444-444444444444"


def _fake_page_row(page_number: int, text: str) -> dict[str, object]:
    return {
        "id": f"page-{page_number}",
        "document_id": _DOC_ID,
        "page_number": page_number,
        "text": text,
        "needs_ocr": False,
        "created_at": datetime.now(UTC).isoformat(),
    }


def test_run_extraction_persists_result_and_marks_job_complete() -> None:
    fake_client = MagicMock()
    result = ReportExtractionResult(
        controls=[], cuecs=[], exceptions=[], subservice_organizations=[]
    )

    with (
        patch("app.services.report_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.report_extraction.analysis_jobs_repo") as fake_jobs_repo,
        patch("app.services.report_extraction.report_entities_repo") as fake_entities_repo,
        patch("app.services.report_extraction.ai_client") as fake_ai_client,
    ):
        fake_pages_repo.list_pages.return_value = [_fake_page_row(1, "some report text")]
        fake_jobs_repo.create_job.return_value = "job-1"
        fake_ai_client.call_structured.return_value = result

        run_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_entities_repo.insert_extraction_result.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            document_id=_DOC_ID,
            result=result,
        )
        fake_jobs_repo.set_job_status.assert_called_once_with(
            fake_client, job_id="job-1", status="complete"
        )


def test_run_extraction_marks_requires_review_on_malformed_output() -> None:
    fake_client = MagicMock()

    with (
        patch("app.services.report_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.report_extraction.analysis_jobs_repo") as fake_jobs_repo,
        patch("app.services.report_extraction.report_entities_repo") as fake_entities_repo,
        patch("app.services.report_extraction.ai_client") as fake_ai_client,
    ):
        fake_pages_repo.list_pages.return_value = [_fake_page_row(1, "some report text")]
        fake_jobs_repo.create_job.return_value = "job-1"
        fake_ai_client.call_structured.return_value = None  # malformed/refused

        run_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_entities_repo.insert_extraction_result.assert_not_called()
        fake_jobs_repo.set_job_status.assert_called_once_with(
            fake_client, job_id="job-1", status="requires_review"
        )


def test_run_extraction_with_no_usable_pages_creates_no_jobs() -> None:
    fake_client = MagicMock()

    with (
        patch("app.services.report_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.report_extraction.analysis_jobs_repo") as fake_jobs_repo,
        patch("app.services.report_extraction.ai_client") as fake_ai_client,
    ):
        fake_pages_repo.list_pages.return_value = [
            {**_fake_page_row(1, ""), "needs_ocr": True},
        ]

        run_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_jobs_repo.create_job.assert_not_called()
        fake_ai_client.call_structured.assert_not_called()
