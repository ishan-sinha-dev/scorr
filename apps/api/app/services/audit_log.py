import logging
from typing import Any

from supabase import Client

from app.repositories import audit_log as audit_log_repo

logger = logging.getLogger(__name__)


def record(
    client: Client,
    *,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    organization_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit log write.

    The primary operation (creating the org/audit period) has already
    committed by the time this runs — a logging failure must not turn into
    a 500 for an action that actually succeeded. It's logged instead.
    """
    try:
        audit_log_repo.record(
            client,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            organization_id=organization_id,
            metadata=metadata,
        )
    except Exception:
        logger.exception(
            "Failed to record audit log entry: action=%s entity_type=%s",
            action,
            entity_type,
        )
