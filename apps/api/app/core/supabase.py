from fastapi import Depends
from supabase import Client, create_client

from app.core.config import settings
from app.core.security import AuthUser, get_current_user


def get_user_client(access_token: str) -> Client:
    """Build a Supabase client scoped to the caller's own access token.

    The anon key alone grants nothing; calling `.postgrest.auth(token)`
    makes every subsequent `.table()`/`.rpc()` call on this client carry
    the caller's own JWT, so Postgres RLS policies see the real `auth.uid()`
    — this client can never see or write more than the calling user can.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY are not configured")

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


def get_current_user_client(user: AuthUser = Depends(get_current_user)) -> Client:
    """FastAPI dependency wrapping get_user_client() around the current
    request's authenticated caller. Routes depend on this (not on
    get_user_client directly) so tests can override it via
    app.dependency_overrides instead of monkeypatching the Supabase SDK.
    """
    return get_user_client(user.access_token)
