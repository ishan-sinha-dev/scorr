import logging
from typing import TypeVar

from openai import (
    APIError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAI,
)
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)


def call_structured(model: str, schema: type[T], messages: list[dict[str, str]]) -> T | None:
    """Wraps OpenAI's structured-outputs call (response validated against
    `schema` before it ever reaches this function's caller).

    Retries once (settings.ai_extraction_max_retries) on a schema/refusal
    failure. Returns None — never a malformed object — if it still fails;
    callers persist a requires_review marker on None rather than storing
    anything unvalidated, per the "never silently store malformed AI
    output" rule.
    """
    client = _client()
    attempts = settings.ai_extraction_max_retries + 1
    for attempt in range(1, attempts + 1):
        try:
            completion = client.chat.completions.parse(
                model=model, messages=messages, response_format=schema  # type: ignore[arg-type]
            )
        except (LengthFinishReasonError, ContentFilterFinishReasonError, APIError) as exc:
            logger.warning("Structured output attempt %d/%d failed: %s", attempt, attempts, exc)
            continue

        message = completion.choices[0].message
        if message.refusal or message.parsed is None:
            logger.warning(
                "Structured output attempt %d/%d refused or unparsed: %s",
                attempt,
                attempts,
                message.refusal,
            )
            continue
        return message.parsed
    return None
