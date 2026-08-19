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
