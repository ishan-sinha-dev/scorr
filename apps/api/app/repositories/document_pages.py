from typing import Any, Literal, cast

from supabase import Client

from app.schemas.document_pages import PageExtraction

ExtractionStatus = Literal["pending", "processing", "complete", "failed"]


def set_extraction_status(
    client: Client, *, document_id: str, status: ExtractionStatus, error: str | None = None
) -> None:
    client.table("documents").update(
        {"extraction_status": status, "extraction_error": error}
    ).eq("id", document_id).execute()


def upsert_pages(
    client: Client, *, document_id: str, organization_id: str, pages: list[PageExtraction]
) -> None:
    if not pages:
        return
    client.table("document_pages").upsert(
        [
            {
                "document_id": document_id,
                "organization_id": organization_id,
                "page_number": page.page_number,
                "text": page.text,
                "needs_ocr": page.needs_ocr,
            }
            for page in pages
        ],
        on_conflict="document_id,page_number",
    ).execute()


def list_pages(client: Client, *, document_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("document_pages")
        .select("*")
        .eq("document_id", document_id)
        .order("page_number")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
