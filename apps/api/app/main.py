from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

from app.api.audit_periods import router as audit_periods_router
from app.api.comparison import router as comparison_router
from app.api.control_mappings import router as control_mappings_router
from app.api.documents import router as documents_router
from app.api.findings import router as findings_router
from app.api.health import router as health_router
from app.api.internal_controls import router as internal_controls_router
from app.api.organizations import router as organizations_router
from app.core.config import settings

app = FastAPI(title="SOCRR API", version="0.1.0")

app.include_router(health_router)
app.include_router(organizations_router)
app.include_router(audit_periods_router)
app.include_router(documents_router)
app.include_router(internal_controls_router)
app.include_router(control_mappings_router)
app.include_router(findings_router)
app.include_router(comparison_router)


@app.exception_handler(APIError)
def handle_postgrest_error(_request: Request, exc: APIError) -> JSONResponse:
    """Postgres RLS denials surface here as APIError (SQLSTATE 42501,
    'insufficient_privilege'). Everything else from PostgREST is a 400 —
    this is not a general-purpose error mapper, just enough to avoid
    leaking raw Postgres errors as 500s.
    """
    status_code = 403 if exc.code == "42501" else 400
    return JSONResponse(status_code=status_code, content={"detail": exc.message})


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "socrr-api", "environment": settings.environment}
