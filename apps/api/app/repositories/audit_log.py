from typing import Any

from supabase import Client


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
    client.table("audit_log").insert(
        {
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
        }
    ).execute()
