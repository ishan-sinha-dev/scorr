from typing import Any, cast

from supabase import Client


def insert_review(
    client: Client,
    *,
    organization_id: str,
    finding_id: str,
    reviewer_id: str,
    decision: str,
    override_coverage_status: str | None,
    notes: str | None,
) -> dict[str, Any]:
    response = (
        client.table("finding_reviews")
        .insert(
            {
                "organization_id": organization_id,
                "finding_id": finding_id,
                "reviewer_id": reviewer_id,
                "decision": decision,
                "override_coverage_status": override_coverage_status,
                "notes": notes,
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def list_reviews(client: Client, *, finding_ids: list[str]) -> list[dict[str, Any]]:
    if not finding_ids:
        return []
    response = (
        client.table("finding_reviews")
        .select("*")
        .in_("finding_id", finding_ids)
        .order("created_at")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
