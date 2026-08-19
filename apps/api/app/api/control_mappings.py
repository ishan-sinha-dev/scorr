from fastapi import APIRouter, Depends
from supabase import Client

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.control_mappings import ControlMappingOut, MappingStatusOut
from app.services import control_mappings as control_mappings_service

router = APIRouter(
    prefix="/organizations/{organization_id}/audit-periods/{audit_period_id}",
    tags=["control-mappings"],
)


@router.post("/map-controls", status_code=202)
def map_controls(
    organization_id: str,
    audit_period_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> dict[str, str]:
    control_mappings_service.map_controls(
        client,
        organization_id=organization_id,
        audit_period_id=audit_period_id,
        actor_user_id=user.id,
        access_token=user.access_token,
    )
    return {"status": "queued"}


@router.get("/control-mappings", response_model=list[ControlMappingOut])
def list_control_mappings(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[ControlMappingOut]:
    return control_mappings_service.list_control_mappings(client, audit_period_id=audit_period_id)


@router.get("/mapping-status", response_model=MappingStatusOut)
def get_mapping_status(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> MappingStatusOut:
    return control_mappings_service.get_mapping_status(client, audit_period_id=audit_period_id)
