from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    access_token: str


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    """Module-level singleton so the JWKS response is actually cached
    (PyJWKClient's cache lives on the instance) instead of re-fetched on
    every request."""
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(jwks_url)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthUser:
    """Verify the caller's Supabase access token and return their identity.

    This only authenticates the request. Authorization — which rows the
    caller may see or write — is enforced by Postgres RLS using this same
    token; see app/core/supabase.py. FastAPI never bypasses RLS with a
    service-role key on the caller's behalf.
    """
    token = credentials.credentials
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    return AuthUser(id=payload["sub"], email=payload.get("email"), access_token=token)
