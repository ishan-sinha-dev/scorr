from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized app configuration, loaded from environment variables.

    This is the single place app code reads config from — no os.environ
    calls scattered elsewhere. Fields are added as the phase that needs
    them lands (e.g. no OpenAI model-name config yet: nothing calls
    OpenAI until Phase 5).
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "development"

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    openai_api_key: str | None = None
    # Cheaper model for straightforward structured extraction, per the
    # spec's own cost-control rule ("cheaper models for classification/
    # simple extraction, stronger models only for ambiguous mapping/
    # reasoning"). Centralized here — never hardcoded at a call site — so
    # it can change without touching extraction logic.
    openai_extraction_model: str = "gpt-4o-mini"
    # Chunk size in characters, not tokens — a simple, good-enough proxy
    # that avoids adding a tokenizer dependency just to size chunks: never
    # send a whole report in one prompt (spec section 11), while staying
    # generous enough that a chunk boundary rarely needs to split a single
    # control's description across two chunks.
    ai_chunk_max_chars: int = 12000
    ai_extraction_max_retries: int = 1

    # Phase 7 (control mapping). 1536 dimensions is baked into the
    # database/migrations/0006_control_mapping.sql vector(1536) columns —
    # changing this model means a new column, not swapping this setting.
    openai_embedding_model: str = "text-embedding-3-small"
    # How many nearest-neighbor candidates the vector search hands the LLM
    # per internal control, per entity type (soc_controls/cuecs/exceptions).
    mapping_top_k: int = 5
    # Cosine similarity (1 - cosine distance, range [-1, 1]) below which a
    # vector-search candidate isn't even offered to the LLM for
    # confirmation — a cheap pre-filter, not the final relevance judgment.
    mapping_similarity_threshold: float = 0.75

    redis_url: str = "redis://localhost:6379/0"

    # Document upload (Phase 3). Centralized here, not hardcoded at the
    # call site, so the limit/allowlist can change without touching
    # validation logic.
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50MB
    allowed_upload_content_types: tuple[str, ...] = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    )


settings = Settings()
