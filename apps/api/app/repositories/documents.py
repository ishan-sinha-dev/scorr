import uuid
from typing import Any, cast

from supabase import Client

_BUCKET = "documents"
_SIGNED_URL_TTL_SECONDS = 300


def _object_path(
    organization_id: str, audit_period_id: str, document_id: str, file_name: str
) -> str:
    return f"{organization_id}/{audit_period_id}/{document_id}-{file_name}"


def upload_and_register(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    document_type: str,
    file_name: str,
    content: bytes,
    content_type: str,
    uploaded_by: str,
) -> dict[str, Any]:
    """Uploads to Storage, then inserts the documents row.

    Not one atomic transaction — Storage and Postgres are separate systems
    in Supabase, so there's no RPC-style trick like create_organization()'s
    here. If the table insert fails after a successful upload, the object
    is orphaned in Storage with no documents row pointing at it. Accepted
    for Phase 3: nothing lists Storage directly (only the documents table),
    so an orphan has no application-visible effect — just wasted bytes.
    """
    document_id = str(uuid.uuid4())
    storage_path = _object_path(organization_id, audit_period_id, document_id, file_name)

    client.storage.from_(_BUCKET).upload(
        storage_path, content, file_options={"content-type": content_type}
    )

    response = (
        client.table("documents")
        .insert(
            {
                "id": document_id,
                "organization_id": organization_id,
                "audit_period_id": audit_period_id,
                "document_type": document_type,
                "file_name": file_name,
                "storage_path": storage_path,
                "file_size_bytes": len(content),
                "content_type": content_type,
                "uploaded_by": uploaded_by,
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def list_documents(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("documents")
        .select("*")
        .eq("audit_period_id", audit_period_id)
        .order("created_at")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)


def create_signed_url(client: Client, *, storage_path: str) -> str:
    response = client.storage.from_(_BUCKET).create_signed_url(
        storage_path, _SIGNED_URL_TTL_SECONDS
    )
    url = response.get("signedURL")
    if not url:
        raise RuntimeError(f"Supabase Storage returned no signed URL for {storage_path}")
    return url
