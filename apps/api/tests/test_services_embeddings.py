from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.embeddings import get_embedding


def test_get_embedding_returns_vector_from_openai() -> None:
    original_key = settings.openai_api_key
    settings.openai_api_key = "fake-api-key"
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

    try:
        with patch("app.services.embeddings.OpenAI", return_value=fake_client) as fake_openai_cls:
            result = get_embedding("Reviews access quarterly")
    finally:
        settings.openai_api_key = original_key

    assert result == [0.1, 0.2, 0.3]
    fake_openai_cls.assert_called_once_with(api_key="fake-api-key")
    fake_client.embeddings.create.assert_called_once_with(
        model=settings.openai_embedding_model, input="Reviews access quarterly"
    )


def test_get_embedding_raises_without_api_key() -> None:
    original_key = settings.openai_api_key
    settings.openai_api_key = None
    try:
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_embedding("some text")
    finally:
        settings.openai_api_key = original_key
