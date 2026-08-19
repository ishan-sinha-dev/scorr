from supabase import Client

from app.core.config import settings
from app.repositories import document_pages as document_pages_repo
from app.repositories import internal_controls as internal_controls_repo
from app.schemas.document_pages import DocumentPageOut
from app.schemas.internal_controls import InternalControlExtraction, InternalControlListExtraction
from app.services import ai_client
from app.services.chunking import chunk_pages

_SYSTEM_PROMPT = (
    "You are extracting a customer's internal control framework from a "
    "document excerpt. Identify each individual control described. Every "
    "item must cite the page number it came from (each page in the "
    "excerpt is marked '[Page N]'). If nothing resembling a control "
    "appears in this excerpt, return an empty list — do not invent items."
)


def run_ai_extraction_for_document(
    client: Client, *, organization_id: str, audit_period_id: str, document_id: str
) -> None:
    """AI fallback for PDF/DOCX internal control frameworks, reusing Phase
    5's chunking + ai_client machinery unchanged. HTTP-agnostic — called
    from a Celery task, not a route.
    """
    pages_rows = document_pages_repo.list_pages(client, document_id=document_id)
    pages = [DocumentPageOut.model_validate(row) for row in pages_rows]

    extracted: list[InternalControlExtraction] = []
    for chunk in chunk_pages(pages):
        result = ai_client.call_structured(
            settings.openai_extraction_model,
            InternalControlListExtraction,
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": chunk.text},
            ],
        )
        if result is not None:
            extracted.extend(result.controls)

    internal_controls_repo.insert_ai_extracted(
        client,
        organization_id=organization_id,
        audit_period_id=audit_period_id,
        document_id=document_id,
        controls=extracted,
    )
