from fastapi import APIRouter, Depends
from supabase import Client

from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.organizations import OrganizationCreate, OrganizationOut
from app.services import organizations as organizations_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(
    payload: OrganizationCreate,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> OrganizationOut:
    return organizations_service.create_organization(
        client, actor_user_id=user.id, name=payload.name
    )


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    client: Client = Depends(get_current_user_client),
) -> list[OrganizationOut]:
    return organizations_service.list_my_organizations(client)
