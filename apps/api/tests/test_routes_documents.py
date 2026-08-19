"""Route-level tests with the Supabase client dependency mocked.

Same approach as test_routes_organizations.py / test_routes_audit_periods.py
— proves route -> service -> repository wiring and validation, not real
RLS/Storage enforcement (Storage policies can't be exercised without a real
Supabase project; see database/migrations/0002_documents.sql).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

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
