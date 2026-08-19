from typing import Any, cast

from supabase import Client


def upsert_finding(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    internal_control_id: str,
    control_mapping_id: str | None,
    coverage_status: str,
    risk_level: str,
    confidence: float,
    reasoning: str,
) -> dict[str, Any]:
    """One current finding per control — recompute upserts on the
    internal_control_id unique constraint (0007), never accumulates
    history/versions (out of scope)."""
    response = (
        client.table("findings")
        .upsert(
            {
                "organization_id": organization_id,
                "audit_period_id": audit_period_id,
                "internal_control_id": internal_control_id,
                "control_mapping_id": control_mapping_id,
                "coverage_status": coverage_status,
                "risk_level": risk_level,
                "confidence": confidence,
                "reasoning": reasoning,
            },
            on_conflict="internal_control_id",
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def list_findings(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("findings")
        .select("*")
        .eq("audit_period_id", audit_period_id)
        .order("created_at")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
