import logging

from app.core.supabase import get_user_client
from app.repositories import document_pages as document_pages_repo
from app.repositories import documents as documents_repo
from app.services import audit_log
from app.services.extraction import extract_pages
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="extraction.extract_document")  # type: ignore[untyped-decorator]
def extract_document_task(document_id: str, access_token: str) -> None:
    """Turns an uploaded document's bytes into page-scoped extracted text.

    A Celery task has no HTTP request of its own to carry auth, so the
    enqueuing route passes the caller's own access token through and this
    task builds the same RLS-scoped client an HTTP request would use
    (get_user_client) — never a service-role bypass.

    Known limitation, not silently handled: if this task retries or sits
    queued past the token's expiry, get_user_client's calls will start
    failing with 401. No retry is implemented in v1, so this hasn't come up
    in practice yet.
    """
    client = get_user_client(access_token)
    document_pages_repo.set_extraction_status(client, document_id=document_id, status="processing")
    row = documents_repo.get_document(client, document_id=document_id)
    try:
        content = documents_repo.download(client, storage_path=row["storage_path"])
        pages = extract_pages(row["content_type"], content)
        document_pages_repo.upsert_pages(
            client,
            document_id=document_id,
            organization_id=row["organization_id"],
            pages=pages,
        )
        document_pages_repo.set_extraction_status(
            client, document_id=document_id, status="complete"
        )
        audit_log.record(
            client,
            actor_user_id=row["uploaded_by"],
            action="document.extracted",
            entity_type="document",
            entity_id=document_id,
            organization_id=row["organization_id"],
            metadata={
                "page_count": len(pages),
                "needs_ocr_count": sum(1 for page in pages if page.needs_ocr),
            },
        )
    except Exception as exc:
        logger.exception("Document extraction failed: document_id=%s", document_id)
        document_pages_repo.set_extraction_status(
            client, document_id=document_id, status="failed", error=str(exc)[:500]
        )
