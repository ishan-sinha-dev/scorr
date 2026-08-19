"""JWT verification, tested against a locally-generated keypair — no
network call to a real Supabase JWKS endpoint. _jwks_client() is patched to
return our test key instead of fetching one."""

import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import get_current_user

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _make_token(**claim_overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "sub": _USER_ID,
        "email": "alice@example.com",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256")


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _patched_jwks_client() -> Any:
    fake_jwks_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=_PUBLIC_KEY)
    )
    return patch("app.core.security._jwks_client", return_value=fake_jwks_client)


def test_valid_token_returns_auth_user() -> None:
    token = _make_token()
    with _patched_jwks_client():
        user = get_current_user(_credentials(token))

    assert user.id == _USER_ID
    assert user.email == "alice@example.com"
    assert user.access_token == token


def test_expired_token_is_rejected() -> None:
    token = _make_token(exp=int(time.time()) - 10)
    with _patched_jwks_client(), pytest.raises(HTTPException) as exc_info:
        get_current_user(_credentials(token))

    assert exc_info.value.status_code == 401


def test_wrong_audience_is_rejected() -> None:
    token = _make_token(aud="some-other-service")
    with _patched_jwks_client(), pytest.raises(HTTPException) as exc_info:
        get_current_user(_credentials(token))

    assert exc_info.value.status_code == 401


def test_tampered_signature_is_rejected() -> None:
    token = _make_token()
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with _patched_jwks_client(), pytest.raises(HTTPException) as exc_info:
        get_current_user(_credentials(tampered))

    assert exc_info.value.status_code == 401
