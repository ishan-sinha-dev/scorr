import io

from openpyxl import Workbook
from openpyxl.styles import Font
from supabase import Client

from app.repositories import audit_periods as audit_periods_repo
from app.schemas.findings import FindingOut
from app.services import findings as findings_service

_HEADERS = [
    "Control ID",
    "Description",
    "AI Coverage",
    "Effective Coverage",
    "Confidence",
    "Reviewed",
    "Review Decision",
    "Reasoning",
    "Evidence",
]


def build_findings_workbook(findings: list[FindingOut], *, audit_period_name: str) -> bytes:
    """Pure — takes already-assembled findings (the same data the API
    returns) and produces the workbook bytes. No I/O of its own, so it's
    unit-testable without a fake Supabase client."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Findings"[:31]

    sheet.append([f"Findings — {audit_period_name}"])
    sheet.append([])
    sheet.append(_HEADERS)
    for cell in sheet[3]:
        cell.font = Font(bold=True)

    for finding in findings:
        evidence_text = "; ".join(
            f"{item.file_name} p.{item.page_number}: {item.excerpt}" for item in finding.evidence
        )
        sheet.append(
            [
                finding.internal_control_code or "",
                finding.internal_control_description,
                finding.coverage_status,
                finding.effective_coverage_status,
                round(finding.confidence, 2),
                "Yes" if finding.latest_review else "No",
                finding.latest_review.decision if finding.latest_review else "",
                finding.reasoning,
                evidence_text,
            ]
        )

    for index, header in enumerate(_HEADERS, start=1):
        sheet.column_dimensions[sheet.cell(row=3, column=index).column_letter].width = min(
            max(len(header) + 2, 14), 60
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def generate_findings_export(client: Client, *, audit_period_id: str) -> bytes:
    period = audit_periods_repo.get_audit_period(client, audit_period_id=audit_period_id)
    findings = findings_service.list_findings(client, audit_period_id=audit_period_id)
    return build_findings_workbook(findings, audit_period_name=period["name"])
