from supabase import Client

from app.core.config import settings
from app.repositories import analysis_jobs as analysis_jobs_repo
from app.repositories import document_pages as document_pages_repo
from app.repositories import report_entities as report_entities_repo
from app.schemas.ai_extraction import ReportExtractionResult
from app.schemas.document_pages import DocumentPageOut
from app.services import ai_client
from app.services.chunking import chunk_pages

_SYSTEM_PROMPT = (
    "You are extracting structured facts from an excerpt of a SOC 1/SOC 2 "
    "report. Identify SOC controls, complementary user entity controls "
    "(CUECs), control exceptions, and subservice organizations mentioned "
    "in the text. Every item you extract must cite the exact page number "
    "it came from (each page in the excerpt is marked '[Page N]') and a "
    "short verbatim excerpt as evidence. If nothing of a given category "
    "appears in this excerpt, return an empty list for it — do not invent "
    "items."
)


def run_extraction_for_document(
    client: Client, *, organization_id: str, audit_period_id: str, document_id: str
) -> None:
    """Runs the staged structured-extraction stage over every chunk of a
    document's extracted pages (Phase 4 output). HTTP-agnostic — called
    from a Celery task, not a route.
    """
    pages_rows = document_pages_repo.list_pages(client, document_id=document_id)
    pages = [DocumentPageOut.model_validate(row) for row in pages_rows]
    chunks = chunk_pages(pages)

    for index, chunk in enumerate(chunks):
        job_id = analysis_jobs_repo.create_job(
            client,
            organization_id=organization_id,
            document_id=document_id,
            chunk_index=index,
            status="processing",
        )
        result = ai_client.call_structured(
            settings.openai_extraction_model,
            ReportExtractionResult,
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": chunk.text},
            ],
        )
        if result is None:
            analysis_jobs_repo.set_job_status(client, job_id=job_id, status="requires_review")
            continue
        report_entities_repo.insert_extraction_result(
            client,
            organization_id=organization_id,
            audit_period_id=audit_period_id,
            document_id=document_id,
            result=result,
        )
        analysis_jobs_repo.set_job_status(client, job_id=job_id, status="complete")
