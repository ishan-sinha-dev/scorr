import logging

from app.core.supabase import get_user_client
from app.services import audit_log
from app.services.control_mapping import run_mapping_for_audit_period
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mapping.run_control_mapping")  # type: ignore[untyped-decorator]
def run_control_mapping(
    organization_id: str, audit_period_id: str, actor_user_id: str, access_token: str
) -> None:
    """Runs Phase 7's embedding backfill + vector-search + LLM-confirmation
    mapping pass over every internal control in an audit period.
    Per-control failures are handled inside run_mapping_for_audit_period
    (a failed LLM call persists a requires_review row, never silently
    dropped) — this try/except only covers a total failure (e.g. missing
    OPENAI_API_KEY), audit-logged the same way run_structured_extraction's
    total-failure path is.
    """
    client = get_user_client(access_token)
    try:
        run_mapping_for_audit_period(
            client, organization_id=organization_id, audit_period_id=audit_period_id
        )
    except Exception:
        logger.exception(
            "Control mapping failed entirely: audit_period_id=%s", audit_period_id
        )
        audit_log.record(
            client,
            actor_user_id=actor_user_id,
            action="audit_period.control_mapping_failed",
            entity_type="audit_period",
            entity_id=audit_period_id,
            organization_id=organization_id,
        )
        raise
