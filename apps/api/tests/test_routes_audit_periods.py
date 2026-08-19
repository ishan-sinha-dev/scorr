from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.main import app

client = TestClient(app)

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_FAKE_USER = AuthUser(
    id="11111111-1111-1111-1111-111111111111",
    email="alice@example.com",
    access_token="fake-access-token",
)


def _override_user() -> AuthUser:
    return _FAKE_USER


def test_create_audit_period_returns_201() -> None:
    fake_row = {
        "id": "33333333-3333-3333-3333-333333333333",
        "organization_id": _ORG_ID,
        "name": "FY2026",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "created_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [fake_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.post(
            f"/organizations/{_ORG_ID}/audit-periods",
            json={"name": "FY2026", "period_start": "2026-01-01", "period_end": "2026-12-31"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["name"] == "FY2026"


def test_create_audit_period_rejects_invalid_range() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            f"/organizations/{_ORG_ID}/audit-periods",
            json={"name": "FY2026", "period_start": "2026-12-31", "period_end": "2026-01-01"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_delete_audit_period_returns_204() -> None:
    period_id = "33333333-3333-3333-3333-333333333333"
    fake_row = {
        "id": period_id,
        "organization_id": _ORG_ID,
        "name": "FY2026",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "created_by": _FAKE_USER.id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    fake_table = fake_client.table.return_value
    fake_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        fake_row
    )
    fake_table.delete.return_value.eq.return_value.execute.return_value.data = [fake_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.delete(f"/organizations/{_ORG_ID}/audit-periods/{period_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204


def test_delete_audit_period_rejects_non_creator_non_owner() -> None:
    # RLS-scoped delete matches zero rows for a member who's neither the
    # creator nor an org owner — must surface as 403, never a silent 204.
    period_id = "33333333-3333-3333-3333-333333333333"
    fake_row = {
        "id": period_id,
        "organization_id": _ORG_ID,
        "name": "FY2026",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "created_by": "99999999-9999-9999-9999-999999999999",
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    fake_table = fake_client.table.return_value
    fake_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        fake_row
    )
    fake_table.delete.return_value.eq.return_value.execute.return_value.data = []

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.delete(f"/organizations/{_ORG_ID}/audit-periods/{period_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
