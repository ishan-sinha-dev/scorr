from typing import Any, cast

from supabase import Client


def create_organization(client: Client, name: str) -> dict[str, Any]:
    """Calls the create_organization() RPC, which atomically inserts the
    org and the caller's owner membership (see the Phase 2 migration).

    NOTE: PostgREST's response shape for an RPC returning a single
    composite row (vs. `returns setof`) hasn't been verified against a
    live Supabase project yet — normalized here to accept either a bare
    object or a one-element list. Revisit once a real project exists.
    The `cast` below is this function's boundary between postgrest-py's
    untyped JSON response and our internal typed shape — Pydantic
    (OrganizationOut.model_validate) is what actually validates it.
    """
    response = client.rpc("create_organization", {"org_name": name}).execute()
    data = response.data
    row = data[0] if isinstance(data, list) else data
    return cast(dict[str, Any], row)


def list_organizations(client: Client) -> list[dict[str, Any]]:
    response = client.table("organizations").select("*").order("created_at").execute()
    return cast(list[dict[str, Any]], response.data)
