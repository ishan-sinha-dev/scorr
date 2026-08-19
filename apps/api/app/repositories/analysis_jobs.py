from typing import Any, Literal, cast

from supabase import Client

JobStatus = Literal["pending", "processing", "complete", "failed", "requires_review"]


def create_job(
    client: Client,
    *,
    organization_id: str,
    document_id: str,
    chunk_index: int,
    status: JobStatus,
) -> str:
    response = (
        client.table("analysis_jobs")
        .insert(
            {
                "organization_id": organization_id,
                "document_id": document_id,
                "job_type": "structured_extraction",
                "chunk_index": chunk_index,
                "status": status,
            }
        )
        .execute()
    )
    row = cast(dict[str, Any], response.data[0])
    return cast(str, row["id"])


def set_job_status(
    client: Client, *, job_id: str, status: JobStatus, error: str | None = None
) -> None:
    client.table("analysis_jobs").update({"status": status, "error": error}).eq(
        "id", job_id
    ).execute()


def list_jobs(client: Client, *, document_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("analysis_jobs")
        .select("*")
        .eq("document_id", document_id)
        .order("chunk_index")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
