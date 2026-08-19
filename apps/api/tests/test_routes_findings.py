"""Route-level tests with the Supabase client dependency mocked, same
approach as test_routes_control_mappings.py."""

from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.main import app
from app.schemas.findings import FindingOut

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


def test_compute_findings_returns_count() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        with patch("app.services.findings.compute_findings", return_value=3) as fake_compute:
            response = client.post(f"{_BASE_URL}/compute-findings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "computed", "finding_count": 3}
    fake_compute.assert_called_once_with(
        ANY,
        organization_id=_ORG_ID,
        audit_period_id=_PERIOD_ID,
        actor_user_id=_FAKE_USER.id,
    )


def test_list_findings_returns_rows() -> None:
    fake_finding = FindingOut(
        id="finding-1",
        internal_control_id="ic-1",
        internal_control_code="IC-01",
        internal_control_description="Reviews access quarterly",
        coverage_status="FULL",
        confidence=0.9,
        reasoning="Directly implements the requirement.",
        created_at=datetime.now(UTC),
        evidence=[],
        effective_coverage_status="FULL",
        risk_level="LOW",
        effective_risk_level="LOW",
    )

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        with patch("app.services.findings.list_findings", return_value=[fake_finding]):
            response = client.get(f"{_BASE_URL}/findings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["coverage_status"] == "FULL"


def test_findings_require_authentication() -> None:
    response = client.get(f"{_BASE_URL}/findings")
    assert response.status_code in (401, 403)


def test_review_finding_approve_returns_201() -> None:
    finding_id = "finding-1"
    fake_row = {
        "id": "review-1",
        "finding_id": finding_id,
        "reviewer_id": _FAKE_USER.id,
        "decision": "approved",
        "override_coverage_status": None,
        "notes": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [fake_row]

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_client
    try:
        response = client.post(
            f"{_BASE_URL}/findings/{finding_id}/review", json={"decision": "approved"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["decision"] == "approved"


def test_review_finding_override_requires_status() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            f"{_BASE_URL}/findings/finding-1/review", json={"decision": "overridden"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_review_finding_approved_rejects_override_status() -> None:
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_user_client] = lambda: MagicMock()
    try:
        response = client.post(
            f"{_BASE_URL}/findings/finding-1/review",
            json={"decision": "approved", "override_coverage_status": "FULL"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
