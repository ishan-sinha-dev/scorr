from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check. No dependencies queried — Phase 1 has none yet."""
    return {"status": "ok"}
