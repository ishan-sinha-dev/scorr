from fastapi import APIRouter, Depends, Response
from supabase import Client

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.finding_reviews import FindingReviewCreate, FindingReviewOut
from app.schemas.findings import FindingOut
from app.services import export as export_service
from app.services import finding_reviews as finding_reviews_service
from app.services import findings as findings_service

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter(
    prefix="/organizations/{organization_id}/audit-periods/{audit_period_id}",
    tags=["findings"],
)


@router.post("/compute-findings")
def compute_findings(
    organization_id: str,
    audit_period_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> dict[str, int | str]:
    count = findings_service.compute_findings(
        client,
        organization_id=organization_id,
        audit_period_id=audit_period_id,
        actor_user_id=user.id,
    )
    return {"status": "computed", "finding_count": count}


@router.get("/findings", response_model=list[FindingOut])
def list_findings(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[FindingOut]:
    return findings_service.list_findings(client, audit_period_id=audit_period_id)


@router.get("/findings/export.xlsx")
def export_findings(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> Response:
    content = export_service.generate_findings_export(client, audit_period_id=audit_period_id)
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="findings.xlsx"'},
    )


@router.post("/findings/{finding_id}/review", response_model=FindingReviewOut, status_code=201)
def review_finding(
    organization_id: str,
    audit_period_id: str,
    finding_id: str,
    payload: FindingReviewCreate,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> FindingReviewOut:
    return finding_reviews_service.record_review(
        client,
        organization_id=organization_id,
        finding_id=finding_id,
        reviewer_id=user.id,
        payload=payload,
    )
