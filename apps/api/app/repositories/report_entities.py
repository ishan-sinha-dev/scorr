from typing import Any, cast

from supabase import Client

from app.schemas.ai_extraction import ReportExtractionResult


def insert_extraction_result(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    result: ReportExtractionResult,
) -> None:
    """Bulk-inserts all 4 entity categories from one chunk's structured
    extraction result. A category with no items simply isn't inserted —
    no consumer for an empty insert call."""
    base = {
        "organization_id": organization_id,
        "audit_period_id": audit_period_id,
        "document_id": document_id,
    }

    if result.controls:
        client.table("soc_controls").insert(
            [
                {
                    **base,
                    "page_number": item.page_number,
                    "control_code": item.control_code,
                    "description": item.description,
                    "excerpt": item.excerpt,
                    "confidence": item.confidence,
                }
                for item in result.controls
            ]
        ).execute()

    if result.cuecs:
        client.table("cuecs").insert(
            [
                {
                    **base,
                    "page_number": item.page_number,
                    "description": item.description,
                    "related_control_code": item.related_control_code,
                    "excerpt": item.excerpt,
                    "confidence": item.confidence,
                }
                for item in result.cuecs
            ]
        ).execute()

    if result.exceptions:
        client.table("exceptions").insert(
            [
                {
                    **base,
                    "page_number": item.page_number,
                    "description": item.description,
                    "related_control_code": item.related_control_code,
                    "excerpt": item.excerpt,
                    "confidence": item.confidence,
                }
                for item in result.exceptions
            ]
        ).execute()

    if result.subservice_organizations:
        client.table("subservice_organizations").insert(
            [
                {
                    **base,
                    "page_number": item.page_number,
                    "name": item.name,
                    "description": item.description,
                    "excerpt": item.excerpt,
                    "confidence": item.confidence,
                }
                for item in result.subservice_organizations
            ]
        ).execute()


def list_soc_controls(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("soc_controls").select("*").eq("audit_period_id", audit_period_id).execute()
    )
    return cast(list[dict[str, Any]], response.data)


def list_cuecs(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = client.table("cuecs").select("*").eq("audit_period_id", audit_period_id).execute()
    return cast(list[dict[str, Any]], response.data)


def list_exceptions(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("exceptions").select("*").eq("audit_period_id", audit_period_id).execute()
    )
    return cast(list[dict[str, Any]], response.data)


def list_subservice_organizations(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("subservice_organizations")
        .select("*")
        .eq("audit_period_id", audit_period_id)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
