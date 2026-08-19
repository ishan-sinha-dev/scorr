from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.internal_controls import InternalControlOut
from app.services import documents as documents_service
from app.services import internal_controls as internal_controls_service

router = APIRouter(
    prefix="/organizations/{organization_id}/audit-periods/{audit_period_id}",
    tags=["internal-controls"],
)


@router.get("/internal-controls", response_model=list[InternalControlOut])
def list_internal_controls(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[InternalControlOut]:
    return internal_controls_service.list_internal_controls(
        client, audit_period_id=audit_period_id
    )


@router.post("/documents/{document_id}/parse-internal-controls")
def parse_internal_controls(
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> dict[str, str]:
    document = documents_service.get_document(client, document_id=document_id)
    if document.document_type != "internal_control_framework":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot parse internal controls for document_type={document.document_type!r}",
        )
    result = internal_controls_service.parse_internal_controls(
        client, document_id=document_id, access_token=user.access_token
    )
    return {"status": result}


@router.post("/carry-forward-controls")
def carry_forward_controls(
    organization_id: str,
    audit_period_id: str,
    from_audit_period_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> dict[str, int | str]:
    count = internal_controls_service.carry_forward_controls(
        client,
        organization_id=organization_id,
        from_audit_period_id=from_audit_period_id,
        to_audit_period_id=audit_period_id,
        actor_user_id=user.id,
    )
    return {"status": "copied", "control_count": count}
