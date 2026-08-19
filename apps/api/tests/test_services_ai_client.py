"""ai_client wraps the OpenAI SDK's structured-outputs call. _client() is
patched to a MagicMock rather than hitting the network — same approach as
the Supabase client tests elsewhere in this suite."""

from unittest.mock import MagicMock, patch

import pytest
from openai import APIError
from pydantic import BaseModel

from app.core.config import settings
from app.services import ai_client


class _Foo(BaseModel):
    value: int


def test_call_structured_returns_parsed_object_on_success() -> None:
    fake_client = MagicMock()
    completion = MagicMock()
    completion.choices[0].message.refusal = None
    completion.choices[0].message.parsed = _Foo(value=42)
    fake_client.chat.completions.parse.return_value = completion

    with patch("app.services.ai_client._client", return_value=fake_client):
        result = ai_client.call_structured(
            "gpt-4o-mini", _Foo, [{"role": "user", "content": "hi"}]
        )

    assert result == _Foo(value=42)
    fake_client.chat.completions.parse.assert_called_once()


def test_call_structured_returns_none_after_refusal_exhausts_retries() -> None:
    fake_client = MagicMock()
    completion = MagicMock()
    completion.choices[0].message.refusal = "cannot help with that"
    completion.choices[0].message.parsed = None
    fake_client.chat.completions.parse.return_value = completion

    with patch("app.services.ai_client._client", return_value=fake_client):
        result = ai_client.call_structured(
            "gpt-4o-mini", _Foo, [{"role": "user", "content": "hi"}]
        )

    assert result is None
    assert fake_client.chat.completions.parse.call_count == settings.ai_extraction_max_retries + 1


def test_call_structured_retries_once_then_succeeds() -> None:
    fake_client = MagicMock()
    bad = MagicMock()
    bad.choices[0].message.refusal = "no"
    bad.choices[0].message.parsed = None
    good = MagicMock()
    good.choices[0].message.refusal = None
    good.choices[0].message.parsed = _Foo(value=7)
    fake_client.chat.completions.parse.side_effect = [bad, good]

    with patch("app.services.ai_client._client", return_value=fake_client):
        result = ai_client.call_structured(
            "gpt-4o-mini", _Foo, [{"role": "user", "content": "hi"}]
        )

    assert result == _Foo(value=7)
    assert fake_client.chat.completions.parse.call_count == 2


def test_call_structured_returns_none_on_api_error() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.parse.side_effect = APIError(
        "boom", request=MagicMock(), body=None
    )

    with patch("app.services.ai_client._client", return_value=fake_client):
        result = ai_client.call_structured(
            "gpt-4o-mini", _Foo, [{"role": "user", "content": "hi"}]
        )

    assert result is None


def test_call_structured_raises_without_api_key() -> None:
    original_key = settings.openai_api_key
    settings.openai_api_key = None
    try:
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            ai_client.call_structured("gpt-4o-mini", _Foo, [{"role": "user", "content": "hi"}])
    finally:
        settings.openai_api_key = original_key
