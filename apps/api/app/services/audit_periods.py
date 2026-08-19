from supabase import Client

from app.repositories import audit_periods as audit_periods_repo
from app.schemas.audit_periods import AuditPeriodCreate, AuditPeriodOut
from app.services import audit_log


def create_audit_period(
    client: Client,
    *,
    organization_id: str,
    actor_user_id: str,
    payload: AuditPeriodCreate,
) -> AuditPeriodOut:
    row = audit_periods_repo.create_audit_period(
        client,
        organization_id=organization_id,
        name=payload.name,
        period_start=payload.period_start.isoformat(),
        period_end=payload.period_end.isoformat(),
        created_by=actor_user_id,
    )
    period = AuditPeriodOut.model_validate(row)
    audit_log.record(
        client,
        actor_user_id=actor_user_id,
        action="audit_period.created",
        entity_type="audit_period",
        entity_id=period.id,
        organization_id=organization_id,
        metadata={"name": period.name},
    )
    return period


def list_audit_periods(client: Client, *, organization_id: str) -> list[AuditPeriodOut]:
    rows = audit_periods_repo.list_audit_periods(client, organization_id=organization_id)
    return [AuditPeriodOut.model_validate(row) for row in rows]
