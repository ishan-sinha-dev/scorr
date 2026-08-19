from datetime import UTC, datetime
from typing import Any, cast

from supabase import Client

# Embedding backfill is the same shape across internal_controls/soc_controls/
# cuecs/exceptions (an id + a text column + a nullable embedding column) —
# one parameterized pair of functions rather than four near-identical
# copies, one per table.


def list_rows_missing_embedding(
    client: Client, *, table: str, audit_period_id: str, text_column: str
) -> list[dict[str, Any]]:
    response = (
        client.table(table)
        .select(f"id,{text_column}")
        .eq("audit_period_id", audit_period_id)
        .is_("embedding", "null")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def set_embedding(client: Client, *, table: str, row_id: str, embedding: list[float]) -> None:
    client.table(table).update({"embedding": embedding}).eq("id", row_id).execute()


def mark_mapping_attempted(client: Client, *, internal_control_id: str) -> None:
    client.table("internal_controls").update(
        {"mapping_attempted_at": datetime.now(UTC).isoformat()}
    ).eq("id", internal_control_id).execute()


def delete_control_mappings_for_internal_control(
    client: Client, *, internal_control_id: str
) -> None:
    # control_mapping_cuecs/control_mapping_exceptions both reference
    # control_mapping_id ON DELETE CASCADE (0006_control_mapping.sql), so
    # deleting here also clears their rows for this control. Called at the
    # top of each control's mapping pass so re-clicking "Map controls" is
    # idempotent — this run's outcome fully replaces the last one, instead
    # of a second insert hitting control_mappings' unique(internal_control_id,
    # soc_control_id) constraint and aborting the whole task partway through.
    client.table("control_mappings").delete().eq(
        "internal_control_id", internal_control_id
    ).execute()


def match_soc_controls(
    client: Client, *, embedding: list[float], audit_period_id: str, match_count: int
) -> list[dict[str, Any]]:
    response = client.rpc(
        "match_soc_controls",
        {
            "query_embedding": embedding,
            "target_audit_period_id": audit_period_id,
            "match_count": match_count,
        },
    ).execute()
    return cast(list[dict[str, Any]], response.data)


def match_cuecs(
    client: Client, *, embedding: list[float], audit_period_id: str, match_count: int
) -> list[dict[str, Any]]:
    response = client.rpc(
        "match_cuecs",
        {
            "query_embedding": embedding,
            "target_audit_period_id": audit_period_id,
            "match_count": match_count,
        },
    ).execute()
    return cast(list[dict[str, Any]], response.data)


def match_exceptions(
    client: Client, *, embedding: list[float], audit_period_id: str, match_count: int
) -> list[dict[str, Any]]:
    response = client.rpc(
        "match_exceptions",
        {
            "query_embedding": embedding,
            "target_audit_period_id": audit_period_id,
            "match_count": match_count,
        },
    ).execute()
    return cast(list[dict[str, Any]], response.data)


def insert_control_mapping(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    internal_control_id: str,
    soc_control_id: str,
    similarity_score: float,
    confidence: float,
    relevance_summary: str,
    requires_review: bool,
) -> str:
    response = (
        client.table("control_mappings")
        .insert(
            {
                "organization_id": organization_id,
                "audit_period_id": audit_period_id,
                "internal_control_id": internal_control_id,
                "soc_control_id": soc_control_id,
                "similarity_score": similarity_score,
                "confidence": confidence,
                "relevance_summary": relevance_summary,
                "requires_review": requires_review,
            }
        )
        .execute()
    )
    row = cast(dict[str, Any], response.data[0])
    return cast(str, row["id"])


def insert_mapping_cuecs(
    client: Client, *, organization_id: str, control_mapping_id: str, cuec_ids: list[str]
) -> None:
    if not cuec_ids:
        return
    client.table("control_mapping_cuecs").insert(
        [
            {
                "organization_id": organization_id,
                "control_mapping_id": control_mapping_id,
                "cuec_id": cuec_id,
            }
            for cuec_id in cuec_ids
        ]
    ).execute()


def insert_mapping_exceptions(
    client: Client, *, organization_id: str, control_mapping_id: str, exception_ids: list[str]
) -> None:
    if not exception_ids:
        return
    client.table("control_mapping_exceptions").insert(
        [
            {
                "organization_id": organization_id,
                "control_mapping_id": control_mapping_id,
                "exception_id": exception_id,
            }
            for exception_id in exception_ids
        ]
    ).execute()


def list_mapping_cuecs(
    client: Client, *, control_mapping_ids: list[str]
) -> list[dict[str, Any]]:
    if not control_mapping_ids:
        return []
    response = (
        client.table("control_mapping_cuecs")
        .select("*")
        .in_("control_mapping_id", control_mapping_ids)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def list_mapping_exceptions(
    client: Client, *, control_mapping_ids: list[str]
) -> list[dict[str, Any]]:
    if not control_mapping_ids:
        return []
    response = (
        client.table("control_mapping_exceptions")
        .select("*")
        .in_("control_mapping_id", control_mapping_ids)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def list_control_mappings(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("control_mappings")
        .select("*")
        .eq("audit_period_id", audit_period_id)
        .order("created_at")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
