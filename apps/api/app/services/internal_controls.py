from typing import Literal

from supabase import Client

from app.repositories import documents as documents_repo
from app.repositories import internal_controls as internal_controls_repo
from app.schemas.internal_controls import InternalControlOut
from app.services import audit_log
from app.services.internal_controls_parser import DETERMINISTIC_CONTENT_TYPES, parse
from app.workers.ai_extraction import extract_internal_controls_ai


def parse_internal_controls(
    client: Client, *, document_id: str, access_token: str
) -> Literal["parsed", "queued"]:
    """Dispatches on content type: XLSX/CSV parse synchronously (fast,
    deterministic — no Celery needed); PDF/DOCX enqueue the AI fallback,
    reusing Phase 4's already-extracted document_pages. HTTP-agnostic — the
    document_type gate lives in app/api/internal_controls.py, matching
    where every other type gate lives.
    """
    row = documents_repo.get_document(client, document_id=document_id)
    if row["content_type"] in DETERMINISTIC_CONTENT_TYPES:
        content = documents_repo.download(client, storage_path=row["storage_path"])
        controls = parse(row["content_type"], content)
        internal_controls_repo.insert_deterministic(
            client,
            organization_id=row["organization_id"],
            audit_period_id=row["audit_period_id"],
            document_id=document_id,
            controls=controls,
        )
        audit_log.record(
            client,
            actor_user_id=row["uploaded_by"],
            action="document.internal_controls_parsed",
            entity_type="document",
            entity_id=document_id,
            organization_id=row["organization_id"],
            metadata={"control_count": len(controls), "extraction_method": "deterministic"},
        )
        return "parsed"

    extract_internal_controls_ai.delay(document_id, access_token)
    return "queued"


def list_internal_controls(client: Client, *, audit_period_id: str) -> list[InternalControlOut]:
    rows = internal_controls_repo.list_internal_controls(client, audit_period_id=audit_period_id)
    return [InternalControlOut.model_validate(row) for row in rows]


def carry_forward_controls(
    client: Client,
    *,
    organization_id: str,
    from_audit_period_id: str,
    to_audit_period_id: str,
    actor_user_id: str,
) -> int:
    """Phase 14 (scoped): copies a prior period's internal_controls into a
    new period, so a stable framework doesn't need re-uploading every
    year. No diffing against the new SOC report and no auto-revalidation
    of existing control_mappings — the copied controls simply go through
    "Map controls" again like any other, same as a freshly parsed set.
    """
    source_controls = internal_controls_repo.list_internal_controls(
        client, audit_period_id=from_audit_period_id
    )
    count = internal_controls_repo.copy_controls(
        client,
        organization_id=organization_id,
        to_audit_period_id=to_audit_period_id,
        source_controls=source_controls,
    )
    audit_log.record(
        client,
        actor_user_id=actor_user_id,
        action="audit_period.controls_carried_forward",
        entity_type="audit_period",
        entity_id=to_audit_period_id,
        organization_id=organization_id,
        metadata={"from_audit_period_id": from_audit_period_id, "control_count": count},
    )
    return count
