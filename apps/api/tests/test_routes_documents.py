"""Route-level tests with the Supabase client dependency mocked.

Same approach as test_routes_organizations.py / test_routes_audit_periods.py
— proves route -> service -> repository wiring and validation, not real
RLS/Storage enforcement (Storage policies can't be exercised without a real
Supabase project; see database/migrations/0002_documents.sql).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.main import app

client = TestClient(app)

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD_ID = "33333333-3333-3333-3333-333333333333"
_DOC_ID = "44444444-4444-4444-4444-444444444444"
_FAKE_USER = AuthUser(
    id="11111111-1111-1111-1111-111111111111",
    email="alice@example.com",
    access_token="fake-access-token",
)
_UPLOAD_URL = f"/organizations/{_ORG_ID}/audit-periods/{_PERIOD_ID}/documents"


def _override_user() -> AuthUser:
    return _FAKE_USER


def _fake_client_for_upload(fake_row: dict[str, object]) -> MagicMock:
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [fake_row]
    fake_client.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://signed.example/report.pdf"
    }
    return fake_client


def test_upload_document_returns_201() -> None:
    fake_row = {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_type": "soc_report",
        "file_name": "report.pdf",
        "storage_path": f"{_ORG_ID}/{_PERIOD_ID}/{_DOC_ID}-report.pdf",
        "file_size_bytes": 7,
        "content_type": "application/pdf",
        "uploaded_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = _fake_client_for_upload(fake_row)

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.documents.extract_document_task") as fake_task:
            response = client.post(
                _UPLOAD_URL,
                data={"document_type": "soc_report"},
                files={"file": ("report.pdf", b"content", "application/pdf")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["file_name"] == "report.pdf"
    assert body["view_url"] == "https://signed.example/report.pdf"
    fake_client.storage.from_.return_value.upload.assert_called_once()
    # PDF is an extractable content type: Phase 4's pipeline must be queued,
    # and the document should already report 'pending' in the response
    # rather than leaving extraction_status NULL until a worker picks it up.
    assert body["extraction_status"] == "pending"
    fake_task.delay.assert_called_once_with(_DOC_ID, _FAKE_USER.access_token)


def test_upload_document_does_not_queue_extraction_for_csv() -> None:
    fake_row = {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_type": "internal_control_framework",
        "file_name": "controls.csv",
        "storage_path": f"{_ORG_ID}/{_PERIOD_ID}/{_DOC_ID}-controls.csv",
        "file_size_bytes": 7,
        "content_type": "text/csv",
        "uploaded_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = _fake_client_for_upload(fake_row)

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.documents.extract_document_task") as fake_task:
            response = client.post(
                _UPLOAD_URL,
                data={"document_type": "internal_control_framework"},
                files={"file": ("controls.csv", b"content", "text/csv")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["extraction_status"] is None
    fake_task.delay.assert_not_called()


def test_upload_document_rejects_unsupported_content_type() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            _UPLOAD_URL,
            data={"document_type": "soc_report"},
            files={"file": ("malware.exe", b"content", "application/octet-stream")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_upload_document_rejects_empty_file() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            _UPLOAD_URL,
            data={"document_type": "soc_report"},
            files={"file": ("report.pdf", b"", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_upload_document_rejects_oversized_file() -> None:
    original_limit = settings.max_upload_size_bytes
    settings.max_upload_size_bytes = 4
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            _UPLOAD_URL,
            data={"document_type": "soc_report"},
            files={"file": ("report.pdf", b"too big", "application/pdf")},
        )
    finally:
        settings.max_upload_size_bytes = original_limit
        app.dependency_overrides.clear()

    assert response.status_code == 413


def test_list_documents_returns_signed_urls() -> None:
    fake_row = {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_type": "bridge_letter",
        "file_name": "bridge.pdf",
        "storage_path": f"{_ORG_ID}/{_PERIOD_ID}/{_DOC_ID}-bridge.pdf",
        "file_size_bytes": 3,
        "content_type": "application/pdf",
        "uploaded_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [fake_row]
    fake_client.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://signed.example/bridge.pdf"
    }

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(_UPLOAD_URL)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["view_url"] == "https://signed.example/bridge.pdf"


def test_documents_require_authentication() -> None:
    response = client.get(_UPLOAD_URL)
    assert response.status_code in (401, 403)


def test_list_document_pages_returns_rows() -> None:
    fake_page = {
        "id": "55555555-5555-5555-5555-555555555555",
        "document_id": _DOC_ID,
        "page_number": 1,
        "text": "Page one text",
        "needs_ocr": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [fake_page]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_UPLOAD_URL}/{_DOC_ID}/pages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["text"] == "Page one text"


def _fake_document_row(
    document_type: str, content_type: str = "application/pdf"
) -> dict[str, object]:
    return {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_type": document_type,
        "file_name": "report.pdf",
        "storage_path": f"{_ORG_ID}/{_PERIOD_ID}/{_DOC_ID}-report.pdf",
        "file_size_bytes": 7,
        "content_type": content_type,
        "uploaded_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def test_analyze_document_queues_for_soc_report() -> None:
    fake_client = MagicMock()
    single_query = fake_client.table.return_value.select.return_value.eq.return_value.single
    single_query.return_value.execute.return_value.data = _fake_document_row("soc_report")
    fake_client.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://signed.example/report.pdf"
    }

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.documents.run_structured_extraction") as fake_task:
            response = client.post(f"{_UPLOAD_URL}/{_DOC_ID}/analyze")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    fake_task.delay.assert_called_once_with(_DOC_ID, _FAKE_USER.access_token)


def test_analyze_document_rejects_internal_control_framework() -> None:
    fake_client = MagicMock()
    single_query = fake_client.table.return_value.select.return_value.eq.return_value.single
    single_query.return_value.execute.return_value.data = _fake_document_row(
        "internal_control_framework", content_type="text/csv"
    )
    fake_client.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://signed.example/controls.csv"
    }

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.documents.run_structured_extraction") as fake_task:
            response = client.post(f"{_UPLOAD_URL}/{_DOC_ID}/analyze")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    fake_task.delay.assert_not_called()


def _fake_jobs_client(job_statuses: list[str]) -> MagicMock:
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [{"status": s} for s in job_statuses]
    return fake_client


def test_analysis_status_reports_processing_while_a_chunk_is_still_running() -> None:
    fake_client = _fake_jobs_client(["complete", "processing"])
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_UPLOAD_URL}/{_DOC_ID}/analysis-status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "processed_chunks": 2}


def test_analysis_status_reports_not_started_before_any_job_exists() -> None:
    fake_client = _fake_jobs_client([])
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_UPLOAD_URL}/{_DOC_ID}/analysis-status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "not_started", "processed_chunks": 0}


def test_analysis_status_reports_complete_once_every_chunk_is_terminal() -> None:
    fake_client = _fake_jobs_client(["complete", "requires_review"])
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_UPLOAD_URL}/{_DOC_ID}/analysis-status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    # "requires_review" outranks a bare "complete" once nothing is still running.
    assert response.json() == {"status": "requires_review", "processed_chunks": 2}
