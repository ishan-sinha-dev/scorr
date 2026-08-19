from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from supabase import Client

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.core.supabase import get_current_user_client
from app.schemas.document_pages import DocumentPageOut
from app.schemas.documents import AnalysisStatusOut, DocumentOut, DocumentType
from app.services import documents as documents_service

router = APIRouter(
    prefix="/organizations/{organization_id}/audit-periods/{audit_period_id}/documents",
    tags=["documents"],
)

_ANALYZABLE_DOCUMENT_TYPES = {"soc_report", "bridge_letter"}


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
        access_token=user.access_token,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    organization_id: str,
    audit_period_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[DocumentOut]:
    return documents_service.list_documents(client, audit_period_id=audit_period_id)


@router.get("/{document_id}/pages", response_model=list[DocumentPageOut])
def list_document_pages(
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    client: Client = Depends(get_current_user_client),
) -> list[DocumentPageOut]:
    return documents_service.list_document_pages(client, document_id=document_id)


@router.post("/{document_id}/analyze", status_code=202)
def analyze_document(
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    user: AuthUser = Depends(get_current_user),
    client: Client = Depends(get_current_user_client),
) -> dict[str, str]:
    document = documents_service.get_document(client, document_id=document_id)
    if document.document_type not in _ANALYZABLE_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot analyze document_type={document.document_type!r}",
        )
    documents_service.analyze_document(
        client, document_id=document_id, access_token=user.access_token
    )
    return {"status": "queued"}


@router.get("/{document_id}/analysis-status", response_model=AnalysisStatusOut)
def get_analysis_status(
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    client: Client = Depends(get_current_user_client),
) -> AnalysisStatusOut:
    return documents_service.get_analysis_status(client, document_id=document_id)
