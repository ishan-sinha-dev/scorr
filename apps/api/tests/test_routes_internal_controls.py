"""Route-level tests with the Supabase client dependency mocked, same
approach as test_routes_documents.py."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

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
_BASE_URL = f"/organizations/{_ORG_ID}/audit-periods/{_PERIOD_ID}"


def _override_user() -> AuthUser:
    return _FAKE_USER


def _fake_document_row(document_type: str, content_type: str) -> dict[str, object]:
    return {
        "id": _DOC_ID,
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_type": document_type,
        "file_name": "controls.csv",
        "storage_path": f"{_ORG_ID}/{_PERIOD_ID}/{_DOC_ID}-controls.csv",
        "file_size_bytes": 7,
        "content_type": content_type,
        "uploaded_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _fake_client_with_document(document_type: str, content_type: str) -> MagicMock:
    fake_client = MagicMock()
    single_query = fake_client.table.return_value.select.return_value.eq.return_value.single
    single_query.return_value.execute.return_value.data = _fake_document_row(
        document_type, content_type
    )
    fake_client.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://signed.example/controls.csv"
    }
    return fake_client


def test_parse_internal_controls_parses_csv_synchronously() -> None:
    fake_client = _fake_client_with_document("internal_control_framework", "text/csv")
    fake_client.storage.from_.return_value.download.return_value = (
        b"description\nReviews access quarterly\n"
    )
    insert_response = fake_client.table.return_value.insert.return_value.execute.return_value
    insert_response.data = [{"id": "row-1"}]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.internal_controls.extract_internal_controls_ai") as fake_task:
            response = client.post(f"{_BASE_URL}/documents/{_DOC_ID}/parse-internal-controls")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "parsed"}
    fake_task.delay.assert_not_called()


def test_parse_internal_controls_queues_ai_extraction_for_pdf() -> None:
    fake_client = _fake_client_with_document("internal_control_framework", "application/pdf")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.internal_controls.extract_internal_controls_ai") as fake_task:
            response = client.post(f"{_BASE_URL}/documents/{_DOC_ID}/parse-internal-controls")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}
    fake_task.delay.assert_called_once_with(_DOC_ID, _FAKE_USER.access_token)


def test_parse_internal_controls_rejects_wrong_document_type() -> None:
    fake_client = _fake_client_with_document("soc_report", "application/pdf")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        with patch("app.services.internal_controls.extract_internal_controls_ai") as fake_task:
            response = client.post(f"{_BASE_URL}/documents/{_DOC_ID}/parse-internal-controls")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    fake_task.delay.assert_not_called()


def test_list_internal_controls_returns_rows() -> None:
    fake_row = {
        "id": "row-1",
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "document_id": _DOC_ID,
        "control_id": "CC1.1",
        "description": "Reviews access quarterly",
        "source_row_ref": "2",
        "extraction_method": "deterministic",
        "requires_review": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [fake_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_BASE_URL}/internal-controls")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["description"] == "Reviews access quarterly"


def test_internal_controls_require_authentication() -> None:
    response = client.get(f"{_BASE_URL}/internal-controls")
    assert response.status_code in (401, 403)


def test_carry_forward_controls_copies_prior_period_rows() -> None:
    from_period_id = "55555555-5555-5555-5555-555555555555"
    source_row = {
        "id": "row-1",
        "organization_id": _ORG_ID,
        "audit_period_id": from_period_id,
        "document_id": _DOC_ID,
        "control_id": "IC-01",
        "description": "Access approval control",
        "source_row_ref": "2",
        "extraction_method": "deterministic",
        "requires_review": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [source_row]
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [source_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.post(
            f"{_BASE_URL}/carry-forward-controls",
            params={"from_audit_period_id": from_period_id},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "copied", "control_count": 1}
