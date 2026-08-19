"""Route-level tests with the Supabase client dependency mocked.

These prove the route -> service -> repository wiring and response
shaping. They do NOT exercise real RLS/tenant isolation — that was
verified separately against a live Postgres instance during Phase 2
development (see docs/architecture/phase0-assessment.md); a fake client
here just returns canned data.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.main import app

client = TestClient(app)

_FAKE_USER = AuthUser(
    id="11111111-1111-1111-1111-111111111111",
    email="alice@example.com",
    access_token="fake-access-token",
)


def _override_user() -> AuthUser:
    return _FAKE_USER


def test_create_organization_returns_201_with_body() -> None:
    fake_org = {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Alice Audit Firm",
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.return_value.data = fake_org

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.post("/organizations", json={"name": "Alice Audit Firm"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["name"] == "Alice Audit Firm"
    fake_client.rpc.assert_called_once_with(
        "create_organization", {"org_name": "Alice Audit Firm"}
    )


def test_create_organization_rejects_blank_name() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post("/organizations", json={"name": ""})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_list_organizations_returns_client_rows() -> None:
    fake_rows = [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Alice Audit Firm",
            "created_at": datetime.now(UTC).isoformat(),
        }
    ]
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value.order.return_value
    query.execute.return_value.data = fake_rows

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.get("/organizations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Alice Audit Firm"]


def test_organizations_require_authentication() -> None:
    # No dependency overrides: the real get_current_user runs and rejects
    # the missing Authorization header before touching Supabase at all.
    response = client.get("/organizations")
    assert response.status_code in (401, 403)
