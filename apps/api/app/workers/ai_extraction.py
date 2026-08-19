import logging

from app.core.supabase import get_user_client
from app.repositories import documents as documents_repo
from app.services import audit_log
from app.services.internal_control_extraction import run_ai_extraction_for_document
from app.services.report_extraction import run_extraction_for_document
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ai_extraction.run_structured_extraction")  # type: ignore[untyped-decorator]
def run_structured_extraction(document_id: str, access_token: str) -> None:
    """Runs Phase 5's structured AI extraction over a document's extracted
    pages. Per-chunk failures are handled inside run_extraction_for_document
    (marked requires_review, never silently dropped) — this try/except
    only covers a total failure (e.g. missing OPENAI_API_KEY), audit-logged
    so there's a persisted signal for "nothing happened and here's why"
    even though there's no per-document analysis_status column.
    """
    client = get_user_client(access_token)
    row = documents_repo.get_document(client, document_id=document_id)
    try:
        run_extraction_for_document(
            client,
            organization_id=row["organization_id"],
            audit_period_id=row["audit_period_id"],
            document_id=document_id,
        )
    except Exception:
        logger.exception("AI extraction failed entirely: document_id=%s", document_id)
        audit_log.record(
            client,
            actor_user_id=row["uploaded_by"],
            action="document.analysis_failed",
            entity_type="document",
            entity_id=document_id,
            organization_id=row["organization_id"],
        )
        raise


@celery_app.task(name="ai_extraction.extract_internal_controls_ai")  # type: ignore[untyped-decorator]
def extract_internal_controls_ai(document_id: str, access_token: str) -> None:
    """AI fallback for PDF/DOCX internal control frameworks — same shape as
    run_structured_extraction above; the actual chunking/extraction logic
    is Phase 5's machinery reused unchanged (see
    app/services/internal_control_extraction.py).
    """
    client = get_user_client(access_token)
    row = documents_repo.get_document(client, document_id=document_id)
    try:
        run_ai_extraction_for_document(
            client,
            organization_id=row["organization_id"],
            audit_period_id=row["audit_period_id"],
            document_id=document_id,
        )
    except Exception:
        logger.exception(
            "Internal control AI extraction failed entirely: document_id=%s", document_id
        )
        audit_log.record(
            client,
            actor_user_id=row["uploaded_by"],
            action="document.internal_controls_extraction_failed",
            entity_type="document",
            entity_id=document_id,
            organization_id=row["organization_id"],
        )
        raise
