from fastapi import Depends
from supabase import Client, ClientOptions, create_client

from app.core.config import settings
from app.core.security import AuthUser, get_current_user


def get_user_client(access_token: str) -> Client:
    """Build a Supabase client scoped to the caller's own access token.

    The token is passed via ClientOptions(headers=...) at construction
    time, not via `client.postgrest.auth(token)` after the fact — the
    supabase-py Client lazily builds each sub-client (postgrest, storage,
    functions) from `self.options.headers` the first time it's accessed,
    and `.postgrest.auth()` only patches the already-built postgrest
    sub-client's own headers. That left `client.storage` requests going
    out with only the anon key and no user JWT, so Storage RLS policies
    always saw an anonymous caller and rejected every upload. Setting the
    Authorization header on ClientOptions up front means every sub-client
    — not just postgrest — carries the caller's own JWT, so Postgres RLS
    and Storage policies both see the real `auth.uid()`.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY are not configured")

    options = ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
    return create_client(settings.supabase_url, settings.supabase_anon_key, options=options)


def get_current_user_client(user: AuthUser = Depends(get_current_user)) -> Client:
    """FastAPI dependency wrapping get_user_client() around the current
    request's authenticated caller. Routes depend on this (not on
    get_user_client directly) so tests can override it via
    app.dependency_overrides instead of monkeypatching the Supabase SDK.
    """
    return get_user_client(user.access_token)
