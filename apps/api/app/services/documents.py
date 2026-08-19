from typing import Literal

from supabase import Client

from app.repositories import analysis_jobs as analysis_jobs_repo
from app.repositories import document_pages as document_pages_repo
from app.repositories import documents as documents_repo
from app.schemas.document_pages import DocumentPageOut
from app.schemas.documents import AnalysisStatusOut, DocumentOut, DocumentType
from app.services import audit_log
from app.services.extraction import EXTRACTABLE_CONTENT_TYPES
from app.workers.ai_extraction import run_structured_extraction
from app.workers.extraction import extract_document_task


def upload_document(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    document_type: DocumentType,
    file_name: str,
    content: bytes,
    content_type: str,
    uploaded_by: str,
    access_token: str,
) -> DocumentOut:
    """HTTP-agnostic: size/content-type validation happens in app/api/documents.py
    before this is called, so this stays reusable by a future background
    worker that isn't behind an HTTP request at all.
    """
    row = documents_repo.upload_and_register(
        client,
        organization_id=organization_id,
        audit_period_id=audit_period_id,
        document_type=document_type,
        file_name=file_name,
        content=content,
        content_type=content_type,
        uploaded_by=uploaded_by,
    )
    audit_log.record(
        client,
        actor_user_id=uploaded_by,
        action="document.uploaded",
        entity_type="document",
        entity_id=row["id"],
        organization_id=organization_id,
        metadata={"file_name": file_name, "document_type": document_type},
    )
    if content_type in EXTRACTABLE_CONTENT_TYPES:
        # Marked 'pending' synchronously, before enqueueing, so the document
        # list shows real state immediately rather than leaving the column
        # NULL (indistinguishable from "not applicable") until a worker
        # happens to pick the task up.
        document_pages_repo.set_extraction_status(client, document_id=row["id"], status="pending")
        row["extraction_status"] = "pending"
        extract_document_task.delay(row["id"], access_token)
    view_url = documents_repo.create_signed_url(client, storage_path=row["storage_path"])
    return DocumentOut.model_validate({**row, "view_url": view_url})


def list_documents(client: Client, *, audit_period_id: str) -> list[DocumentOut]:
    rows = documents_repo.list_documents(client, audit_period_id=audit_period_id)
    return [
        DocumentOut.model_validate(
            {
                **row,
                "view_url": documents_repo.create_signed_url(
                    client, storage_path=row["storage_path"]
                ),
            }
        )
        for row in rows
    ]


def list_document_pages(client: Client, *, document_id: str) -> list[DocumentPageOut]:
    rows = document_pages_repo.list_pages(client, document_id=document_id)
    return [DocumentPageOut.model_validate(row) for row in rows]


def get_document(client: Client, *, document_id: str) -> DocumentOut:
    row = documents_repo.get_document(client, document_id=document_id)
    view_url = documents_repo.create_signed_url(client, storage_path=row["storage_path"])
    return DocumentOut.model_validate({**row, "view_url": view_url})


def analyze_document(client: Client, *, document_id: str, access_token: str) -> None:
    """HTTP-agnostic: the document_type gate (only soc_report/bridge_letter
    are analyzable) lives in app/api/documents.py, matching where Phase 3's
    content-type/size validation lives — this function only enqueues."""
    run_structured_extraction.delay(document_id, access_token)


def get_analysis_status(client: Client, *, document_id: str) -> AnalysisStatusOut:
    """Polled by the frontend while an "Analyze" run is in flight. 'failed'
    takes priority over 'requires_review' over 'complete' — a total-loss
    chunk should never be hidden behind a partial success.
    """
    jobs = analysis_jobs_repo.list_jobs(client, document_id=document_id)
    if not jobs:
        return AnalysisStatusOut(status="not_started", processed_chunks=0)

    statuses = {job["status"] for job in jobs}
    status: Literal["processing", "failed", "requires_review", "complete"]
    if statuses & {"pending", "processing"}:
        status = "processing"
    elif "failed" in statuses:
        status = "failed"
    elif "requires_review" in statuses:
        status = "requires_review"
    else:
        status = "complete"
    return AnalysisStatusOut(status=status, processed_chunks=len(jobs))
