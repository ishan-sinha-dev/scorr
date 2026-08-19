import io
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from openpyxl import load_workbook

from app.schemas.findings import EvidenceRef, FindingOut
from app.services.export import build_findings_workbook, generate_findings_export


def _fake_finding() -> FindingOut:
    return FindingOut(
        id="finding-1",
        internal_control_id="ic-1",
        internal_control_code="IC-01",
        internal_control_description="Access approval control",
        coverage_status="FULL",
        confidence=0.95,
        reasoning="Directly implements the requirement.",
        created_at=datetime.now(UTC),
        evidence=[
            EvidenceRef(
                kind="soc_control",
                document_id="doc-1",
                file_name="soc-report.pdf",
                page_number=4,
                excerpt="Access is approved by a manager.",
                view_url="https://signed.example/soc-report.pdf",
            )
        ],
        effective_coverage_status="FULL",
        risk_level="LOW",
        effective_risk_level="LOW",
    )


def test_build_findings_workbook_writes_one_row_per_finding() -> None:
    content = build_findings_workbook([_fake_finding()], audit_period_name="FY2026")

    workbook = load_workbook(io.BytesIO(content))
    sheet = workbook["Findings"]

    header_row = [cell.value for cell in sheet[3]]
    assert header_row[0] == "Control ID"

    data_row = [cell.value for cell in sheet[4]]
    assert data_row[0] == "IC-01"
    assert data_row[2] == "FULL"
    assert "soc-report.pdf" in data_row[8]


def test_generate_findings_export_fetches_period_name_and_findings() -> None:
    fake_client = MagicMock()
    with (
        patch("app.services.export.audit_periods_repo") as fake_periods_repo,
        patch("app.services.export.findings_service") as fake_findings_service,
    ):
        fake_periods_repo.get_audit_period.return_value = {"id": "period-1", "name": "FY2026"}
        fake_findings_service.list_findings.return_value = [_fake_finding()]

        content = generate_findings_export(fake_client, audit_period_id="period-1")

        assert content.startswith(b"PK")  # xlsx is a zip archive
        fake_periods_repo.get_audit_period.assert_called_once_with(
            fake_client, audit_period_id="period-1"
        )
