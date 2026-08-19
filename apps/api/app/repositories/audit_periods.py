from typing import Any, cast

from supabase import Client


def create_audit_period(
    client: Client,
    *,
    organization_id: str,
    name: str,
    period_start: str,
    period_end: str,
    created_by: str,
) -> dict[str, Any]:
    response = (
        client.table("audit_periods")
        .insert(
            {
                "organization_id": organization_id,
                "name": name,
                "period_start": period_start,
                "period_end": period_end,
                "created_by": created_by,
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def list_audit_periods(client: Client, *, organization_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("audit_periods")
        .select("*")
        .eq("organization_id", organization_id)
        .order("period_start")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def get_audit_period(client: Client, *, audit_period_id: str) -> dict[str, Any]:
    response = (
        client.table("audit_periods").select("*").eq("id", audit_period_id).single().execute()
    )
    return cast(dict[str, Any], response.data)


def delete_audit_period(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    # Returns the deleted row(s) (empty if RLS blocked it — not the
    # creator, not an org owner) so the caller can tell a real delete
    # apart from a silently-filtered no-op, the same class of bug fixed in
    # 0008_documents_update_policy.sql.
    response = client.table("audit_periods").delete().eq("id", audit_period_id).execute()
    return cast(list[dict[str, Any]], response.data)
