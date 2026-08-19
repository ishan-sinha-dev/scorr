from supabase import Client

from app.repositories import documents as documents_repo
from app.schemas.documents import DocumentOut, DocumentType
from app.services import audit_log


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
) -> DocumentOut:
    """HTTP-agnostic: size/content-type validation happens in app/api/documents.py
    before this is called, so this stays reusable by a future background
    worker (Phase 4+) that isn't behind an HTTP request at all.
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
