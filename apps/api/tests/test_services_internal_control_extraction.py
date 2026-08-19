from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.schemas.internal_controls import InternalControlExtraction, InternalControlListExtraction
from app.services.internal_control_extraction import run_ai_extraction_for_document

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


def test_run_ai_extraction_persists_extracted_controls() -> None:
    fake_client = MagicMock()
    result = InternalControlListExtraction(
        controls=[
            InternalControlExtraction(
                control_id="CC1.1", description="Reviews access", page_number=1, confidence=0.9
            )
        ]
    )

    with (
        patch("app.services.internal_control_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.internal_control_extraction.ai_client") as fake_ai_client,
        patch(
            "app.services.internal_control_extraction.internal_controls_repo"
        ) as fake_controls_repo,
    ):
        fake_pages_repo.list_pages.return_value = [_fake_page_row(1, "some framework text")]
        fake_ai_client.call_structured.return_value = result

        run_ai_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_controls_repo.insert_ai_extracted.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            document_id=_DOC_ID,
            controls=result.controls,
        )


def test_run_ai_extraction_skips_malformed_chunk_output() -> None:
    fake_client = MagicMock()

    with (
        patch("app.services.internal_control_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.internal_control_extraction.ai_client") as fake_ai_client,
        patch(
            "app.services.internal_control_extraction.internal_controls_repo"
        ) as fake_controls_repo,
    ):
        fake_pages_repo.list_pages.return_value = [_fake_page_row(1, "some framework text")]
        fake_ai_client.call_structured.return_value = None  # malformed/refused

        run_ai_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_controls_repo.insert_ai_extracted.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            document_id=_DOC_ID,
            controls=[],
        )


def test_run_ai_extraction_with_no_usable_pages_calls_ai_zero_times() -> None:
    fake_client = MagicMock()

    with (
        patch("app.services.internal_control_extraction.document_pages_repo") as fake_pages_repo,
        patch("app.services.internal_control_extraction.ai_client") as fake_ai_client,
        patch(
            "app.services.internal_control_extraction.internal_controls_repo"
        ) as fake_controls_repo,
    ):
        fake_pages_repo.list_pages.return_value = [
            {**_fake_page_row(1, ""), "needs_ocr": True},
        ]

        run_ai_extraction_for_document(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, document_id=_DOC_ID
        )

        fake_ai_client.call_structured.assert_not_called()
        fake_controls_repo.insert_ai_extracted.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            document_id=_DOC_ID,
            controls=[],
        )
