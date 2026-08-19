from supabase import Client

from app.repositories import organizations as organizations_repo
from app.schemas.organizations import OrganizationOut
from app.services import audit_log


def create_organization(client: Client, *, actor_user_id: str, name: str) -> OrganizationOut:
    row = organizations_repo.create_organization(client, name)
    org = OrganizationOut.model_validate(row)
    audit_log.record(
        client,
        actor_user_id=actor_user_id,
        action="organization.created",
        entity_type="organization",
        entity_id=org.id,
        organization_id=org.id,
        metadata={"name": org.name},
    )
    return org


def list_my_organizations(client: Client) -> list[OrganizationOut]:
    rows = organizations_repo.list_organizations(client)
    return [OrganizationOut.model_validate(row) for row in rows]
