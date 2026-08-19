from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from supabase import Client

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.documents import DocumentOut, DocumentType
from app.services import documents as documents_service

router = APIRouter(
    prefix="/organizations/{organization_id}/audit-periods/{audit_period_id}/documents",
    tags=["documents"],
)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    organization_id: str,
    audit_period_id: str,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> DocumentOut:
    if file.content_type not in settings.allowed_upload_content_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported content type: {file.content_type}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="File is empty"
        )
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_bytes} byte limit",
        )

    return documents_service.upload_document(
        client,
        organization_id=organization_id,
        audit_period_id=audit_period_id,
        document_type=document_type,
        file_name=file.filename or "unnamed",
        content=content,
        content_type=file.content_type,
        uploaded_by=user.id,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[DocumentOut]:
    return documents_service.list_documents(client, audit_period_id=audit_period_id)
