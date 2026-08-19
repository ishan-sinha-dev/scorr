from openai import OpenAI

from app.core.config import settings


def get_embedding(text: str) -> list[float]:
    """Wraps OpenAI's embeddings endpoint. Same missing-key guard as
    ai_client._client() — duplicated rather than shared, since the two call
    sites build different SDK resources (chat completions vs. embeddings)
    and the guard is three lines.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=settings.openai_embedding_model, input=text)
    return response.data[0].embedding
