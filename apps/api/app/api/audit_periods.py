from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.audit_periods import AuditPeriodCreate, AuditPeriodOut
from app.services import audit_periods as audit_periods_service

router = APIRouter(prefix="/organizations/{organization_id}/audit-periods", tags=["audit-periods"])


@router.post("", response_model=AuditPeriodOut, status_code=201)
def create_audit_period(
    organization_id: str,
    payload: AuditPeriodCreate,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> AuditPeriodOut:
    return audit_periods_service.create_audit_period(
        client, organization_id=organization_id, actor_user_id=user.id, payload=payload
    )


@router.get("", response_model=list[AuditPeriodOut])
def list_audit_periods(
    organization_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[AuditPeriodOut]:
    return audit_periods_service.list_audit_periods(client, organization_id=organization_id)


@router.delete("/{audit_period_id}", status_code=204)
def delete_audit_period(
    organization_id: str,
    audit_period_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> None:
    try:
        audit_periods_service.delete_audit_period(
            client,
            organization_id=organization_id,
            audit_period_id=audit_period_id,
            actor_user_id=user.id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
