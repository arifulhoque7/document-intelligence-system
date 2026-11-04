from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://docintel:docintel@localhost:5433/docintel"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./storage"

    # Secrets: must be overridden outside local dev.
    jwt_secret: str = "dev-only-change-me"
    # 32 bytes, base64 (urlsafe). Encrypts provider API keys at rest.
    encryption_key: str = "ZGV2LW9ubHktMzItYnl0ZS1lbmNyeXB0aW9uLWtleSE="
    jwt_ttl_minutes: int = 480
    cookie_secure: bool = False
    cors_origins: str = ""  # comma separated; empty when the frontend proxies /api

    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"

    max_file_mb: int = 50
    max_files_per_upload: int = 50
    max_pages: int = 2000
    ocr_dpi: int = 300
    ocr_threads: int = 4
    llm_concurrency: int = 4
    llm_timeout_s: int = 120
    embedding_dim: int = 768

    # Celery runs tasks inline (tests, eval) when true.
    celery_eager: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
