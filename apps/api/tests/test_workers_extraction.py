"""Celery task functions are plain callables — called directly here (not
via .delay()), with get_user_client/repositories mocked, the same
mocked-Supabase-client approach used for the HTTP routes."""

from unittest.mock import MagicMock, patch

from app.schemas.document_pages import PageExtraction
from app.workers.extraction import extract_document_task

_DOC_ID = "44444444-4444-4444-4444-444444444444"
_ORG_ID = "22222222-2222-2222-2222-222222222222"
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _fake_document_row() -> dict[str, object]:
    return {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "storage_path": f"{_ORG_ID}/period/{_DOC_ID}-report.pdf",
        "content_type": "application/pdf",
        "uploaded_by": _USER_ID,
    }


def test_extract_document_task_success_marks_complete() -> None:
    fake_client = MagicMock()
    with (
        patch("app.workers.extraction.get_user_client", return_value=fake_client),
        patch("app.workers.extraction.documents_repo") as fake_documents_repo,
        patch("app.workers.extraction.document_pages_repo") as fake_pages_repo,
        patch("app.workers.extraction.audit_log") as fake_audit_log,
        patch("app.workers.extraction.extract_pages") as fake_extract_pages,
    ):
        fake_documents_repo.get_document.return_value = _fake_document_row()
        fake_documents_repo.download.return_value = b"pdf bytes"
        fake_extract_pages.return_value = [
            PageExtraction(page_number=1, text="hello", needs_ocr=False),
            PageExtraction(page_number=2, text="", needs_ocr=True),
        ]

        extract_document_task(_DOC_ID, "fake-access-token")

        fake_pages_repo.upsert_pages.assert_called_once()
        fake_pages_repo.set_extraction_status.assert_any_call(
            fake_client, document_id=_DOC_ID, status="processing"
        )
        fake_pages_repo.set_extraction_status.assert_called_with(
            fake_client, document_id=_DOC_ID, status="complete"
        )
        fake_audit_log.record.assert_called_once()
        assert fake_audit_log.record.call_args.kwargs["metadata"] == {
            "page_count": 2,
            "needs_ocr_count": 1,
        }


def test_extract_document_task_failure_marks_failed_with_error() -> None:
    fake_client = MagicMock()
    with (
        patch("app.workers.extraction.get_user_client", return_value=fake_client),
        patch("app.workers.extraction.documents_repo") as fake_documents_repo,
        patch("app.workers.extraction.document_pages_repo") as fake_pages_repo,
        patch("app.workers.extraction.audit_log") as fake_audit_log,
    ):
        fake_documents_repo.get_document.return_value = _fake_document_row()
        fake_documents_repo.download.side_effect = RuntimeError("storage unreachable")

        extract_document_task(_DOC_ID, "fake-access-token")

        fake_pages_repo.set_extraction_status.assert_called_with(
            fake_client, document_id=_DOC_ID, status="failed", error="storage unreachable"
        )
        fake_audit_log.record.assert_not_called()
