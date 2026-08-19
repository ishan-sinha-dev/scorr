from fastapi import APIRouter, Depends
from supabase import Client

from app.core.supabase import get_current_user_client
from app.schemas.comparison import AuditPeriodComparison
from app.services import comparison as comparison_service

router = APIRouter(prefix="/organizations/{organization_id}", tags=["comparison"])


@router.get("/compare-audit-periods", response_model=AuditPeriodComparison)
def compare_audit_periods(
    organization_id: str,
    from_audit_period_id: str,
    to_audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> AuditPeriodComparison:
    return comparison_service.compare_audit_periods(
        client,
        from_audit_period_id=from_audit_period_id,
        to_audit_period_id=to_audit_period_id,
    )
