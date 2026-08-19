from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, patch

import pytest

from app.services.findings import (
    compute_findings,
    derive_coverage,
    derive_risk_level,
    list_findings,
)

_ORG_ID = "22222222-2222-2222-2222-222222222222"
_PERIOD_ID = "33333333-3333-3333-3333-333333333333"
_USER_ID = "11111111-1111-1111-1111-111111111111"
_IC_ID = "ic-1"


@pytest.mark.parametrize(
    (
        "mapping_attempted",
        "mapping_count",
        "confirmed_count",
        "has_cuec",
        "has_exception",
        "expected",
    ),
    [
        (False, 0, 0, False, False, None),
        (True, 0, 0, False, False, "NOT_COVERED"),
        (True, 2, 0, False, False, "REQUIRES_REVIEW"),
        (True, 1, 1, True, False, "PARTIAL"),
        (True, 1, 1, False, True, "PARTIAL"),
        (True, 1, 1, False, False, "FULL"),
    ],
)
def test_derive_coverage_table(
    mapping_attempted: bool,
    mapping_count: int,
    confirmed_count: int,
    has_cuec: bool,
    has_exception: bool,
    expected: str | None,
) -> None:
    assert (
        derive_coverage(
            mapping_attempted=mapping_attempted,
            mapping_count=mapping_count,
            confirmed_count=confirmed_count,
            has_linked_cuec=has_cuec,
            has_linked_exception=has_exception,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("NOT_COVERED", "HIGH"),
        ("REQUIRES_REVIEW", "HIGH"),
        ("PARTIAL", "MEDIUM"),
        ("FULL", "LOW"),
        ("NOT_APPLICABLE", "LOW"),
    ],
)
def test_derive_risk_level_table(status: str, expected: str) -> None:
    assert derive_risk_level(status) == expected  # type: ignore[arg-type]


def test_compute_findings_skips_controls_never_mapped() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.findings.internal_controls_repo") as fake_ic_repo,
        patch("app.services.findings.control_mappings_repo") as fake_cm_repo,
        patch("app.services.findings.findings_repo") as fake_findings_repo,
        patch("app.services.findings.audit_log"),
    ):
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access", "mapping_attempted_at": None}
        ]
        fake_cm_repo.list_control_mappings.return_value = []
        fake_cm_repo.list_mapping_cuecs.return_value = []
        fake_cm_repo.list_mapping_exceptions.return_value = []

        written = compute_findings(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, actor_user_id=_USER_ID
        )

        assert written == 0
        fake_findings_repo.upsert_finding.assert_not_called()


def test_compute_findings_writes_not_covered_when_no_mappings_found() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.findings.internal_controls_repo") as fake_ic_repo,
        patch("app.services.findings.control_mappings_repo") as fake_cm_repo,
        patch("app.services.findings.findings_repo") as fake_findings_repo,
        patch("app.services.findings.audit_log"),
    ):
        fake_ic_repo.list_internal_controls.return_value = [
            {
                "id": _IC_ID,
                "description": "Reviews access",
                "mapping_attempted_at": datetime.now(UTC).isoformat(),
            }
        ]
        fake_cm_repo.list_control_mappings.return_value = []
        fake_cm_repo.list_mapping_cuecs.return_value = []
        fake_cm_repo.list_mapping_exceptions.return_value = []

        written = compute_findings(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, actor_user_id=_USER_ID
        )

        assert written == 1
        fake_findings_repo.upsert_finding.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            internal_control_id=_IC_ID,
            control_mapping_id=None,
            coverage_status="NOT_COVERED",
            risk_level="HIGH",
            confidence=0.0,
            reasoning=ANY,
        )


def test_compute_findings_writes_full_for_confirmed_mapping_with_no_links() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.findings.internal_controls_repo") as fake_ic_repo,
        patch("app.services.findings.control_mappings_repo") as fake_cm_repo,
        patch("app.services.findings.findings_repo") as fake_findings_repo,
        patch("app.services.findings.audit_log"),
    ):
        fake_ic_repo.list_internal_controls.return_value = [
            {
                "id": _IC_ID,
                "description": "Reviews access",
                "mapping_attempted_at": datetime.now(UTC).isoformat(),
            }
        ]
        fake_cm_repo.list_control_mappings.return_value = [
            {
                "id": "mapping-1",
                "internal_control_id": _IC_ID,
                "soc_control_id": "sc-1",
                "similarity_score": 0.9,
                "confidence": 0.95,
                "relevance_summary": "Directly implements the requirement.",
                "requires_review": False,
            }
        ]
        fake_cm_repo.list_mapping_cuecs.return_value = []
        fake_cm_repo.list_mapping_exceptions.return_value = []

        written = compute_findings(
            fake_client, organization_id=_ORG_ID, audit_period_id=_PERIOD_ID, actor_user_id=_USER_ID
        )

        assert written == 1
        fake_findings_repo.upsert_finding.assert_called_once_with(
            fake_client,
            organization_id=_ORG_ID,
            audit_period_id=_PERIOD_ID,
            internal_control_id=_IC_ID,
            control_mapping_id="mapping-1",
            coverage_status="FULL",
            risk_level="LOW",
            confidence=0.95,
            reasoning="Directly implements the requirement.",
        )


def test_list_findings_assembles_evidence_from_soc_control_and_documents() -> None:
    fake_client = MagicMock()
    now = datetime.now(UTC).isoformat()
    with (
        patch("app.services.findings.findings_repo") as fake_findings_repo,
        patch("app.services.findings.internal_controls_repo") as fake_ic_repo,
        patch("app.services.findings.control_mappings_repo") as fake_cm_repo,
        patch("app.services.findings.report_entities_repo") as fake_report_entities_repo,
        patch("app.services.findings.documents_repo") as fake_documents_repo,
    ):
        fake_findings_repo.list_findings.return_value = [
            {
                "id": "finding-1",
                "internal_control_id": _IC_ID,
                "control_mapping_id": "mapping-1",
                "coverage_status": "FULL",
                "risk_level": "LOW",
                "confidence": 0.9,
                "reasoning": "Directly implements the requirement.",
                "created_at": now,
            }
        ]
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access"}
        ]
        fake_cm_repo.list_control_mappings.return_value = [
            {"id": "mapping-1", "internal_control_id": _IC_ID, "soc_control_id": "sc-1"}
        ]
        fake_report_entities_repo.list_soc_controls.return_value = [
            {
                "id": "sc-1",
                "document_id": "doc-1",
                "page_number": 4,
                "excerpt": "Access is reviewed quarterly by the security team.",
            }
        ]
        fake_report_entities_repo.list_cuecs.return_value = []
        fake_report_entities_repo.list_exceptions.return_value = []
        fake_documents_repo.list_documents.return_value = [
            {"id": "doc-1", "file_name": "soc-report.pdf", "storage_path": "org/period/doc-1"}
        ]
        fake_documents_repo.create_signed_url.return_value = "https://signed.example/soc-report.pdf"
        fake_cm_repo.list_mapping_cuecs.return_value = []
        fake_cm_repo.list_mapping_exceptions.return_value = []

        results = list_findings(fake_client, audit_period_id=_PERIOD_ID)

        assert len(results) == 1
        finding = results[0]
        assert finding.coverage_status == "FULL"
        assert len(finding.evidence) == 1
        assert finding.evidence[0].file_name == "soc-report.pdf"
        assert finding.evidence[0].page_number == 4
        assert finding.evidence[0].view_url == "https://signed.example/soc-report.pdf"


def test_list_findings_returns_empty_list_when_nothing_computed() -> None:
    fake_client = MagicMock()
    with patch("app.services.findings.findings_repo") as fake_findings_repo:
        fake_findings_repo.list_findings.return_value = []
        assert list_findings(fake_client, audit_period_id=_PERIOD_ID) == []


def test_list_findings_effective_status_reflects_latest_override() -> None:
    fake_client = MagicMock()
    now = datetime.now(UTC).isoformat()
    with (
        patch("app.services.findings.findings_repo") as fake_findings_repo,
        patch("app.services.findings.internal_controls_repo") as fake_ic_repo,
        patch("app.services.findings.control_mappings_repo") as fake_cm_repo,
        patch("app.services.findings.report_entities_repo") as fake_report_entities_repo,
        patch("app.services.findings.documents_repo") as fake_documents_repo,
        patch("app.services.findings.finding_reviews_repo") as fake_reviews_repo,
    ):
        fake_findings_repo.list_findings.return_value = [
            {
                "id": "finding-1",
                "internal_control_id": _IC_ID,
                "control_mapping_id": None,
                "coverage_status": "NOT_COVERED",
                "risk_level": "HIGH",
                "confidence": 0.0,
                "reasoning": "No candidate SOC control was found for this internal control.",
                "created_at": now,
            }
        ]
        fake_ic_repo.list_internal_controls.return_value = [
            {"id": _IC_ID, "description": "Reviews access"}
        ]
        fake_cm_repo.list_control_mappings.return_value = []
        fake_cm_repo.list_mapping_cuecs.return_value = []
        fake_cm_repo.list_mapping_exceptions.return_value = []
        fake_report_entities_repo.list_soc_controls.return_value = []
        fake_report_entities_repo.list_cuecs.return_value = []
        fake_report_entities_repo.list_exceptions.return_value = []
        fake_documents_repo.list_documents.return_value = []
        # Two reviews for the same finding — the second (later) one must win.
        fake_reviews_repo.list_reviews.return_value = [
            {
                "id": "review-1",
                "finding_id": "finding-1",
                "reviewer_id": _USER_ID,
                "decision": "requires_reanalysis",
                "override_coverage_status": None,
                "notes": "checking with the auditor",
                "created_at": now,
            },
            {
                "id": "review-2",
                "finding_id": "finding-1",
                "reviewer_id": _USER_ID,
                "decision": "overridden",
                "override_coverage_status": "NOT_APPLICABLE",
                "notes": "control retired this period",
                "created_at": now,
            },
        ]

        results = list_findings(fake_client, audit_period_id=_PERIOD_ID)

        assert len(results) == 1
        finding = results[0]
        assert finding.coverage_status == "NOT_COVERED"
        assert finding.effective_coverage_status == "NOT_APPLICABLE"
        assert finding.latest_review is not None
        assert finding.latest_review.decision == "overridden"
