"""Route-level tests with the Supabase client dependency mocked, same
approach as test_routes_internal_controls.py."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.main import app

client = TestClient(app)

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD_ID = "33333333-3333-3333-3333-333333333333"
_FAKE_USER = AuthUser(
    id="11111111-1111-1111-1111-111111111111",
    email="alice@example.com",
    access_token="fake-access-token",
)
_BASE_URL = f"/organizations/{_ORG_ID}/audit-periods/{_PERIOD_ID}"


def _override_user() -> AuthUser:
    return _FAKE_USER


def test_map_controls_queues_the_mapping_task() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        with patch("app.services.control_mappings.run_control_mapping") as fake_task:
            response = client.post(f"{_BASE_URL}/map-controls")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {"status": "queued"}
    fake_task.delay.assert_called_once_with(
        _ORG_ID, _PERIOD_ID, _FAKE_USER.id, _FAKE_USER.access_token
    )


def test_list_control_mappings_returns_rows() -> None:
    fake_row = {
        "id": "mapping-1",
        "organization_id": _ORG_ID,
        "audit_period_id": _PERIOD_ID,
        "internal_control_id": "ic-1",
        "soc_control_id": "sc-1",
        "similarity_score": 0.91,
        "confidence": 0.95,
        "relevance_summary": "Directly implements the same requirement.",
        "requires_review": False,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.eq.return_value.order.return_value
    query.execute.return_value.data = [fake_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get(f"{_BASE_URL}/control-mappings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["soc_control_id"] == "sc-1"


def test_control_mappings_require_authentication() -> None:
    response = client.get(f"{_BASE_URL}/control-mappings")
    assert response.status_code in (401, 403)
