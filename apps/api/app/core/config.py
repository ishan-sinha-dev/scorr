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
