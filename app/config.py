from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="fim_", env_file=".env", extra="ignore")


    # OpenAI
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY", "FIM_OPENAI_API_KEY"))
    openai_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("OPENAI_MODEL", "FIM_OPENAI_MODEL"))
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "FIM_OPENAI_BASE_URL"),
    )
    llm_timeout_sec: int = 30

    # Logging
    log_level: str = "INFO"

    # Storage
    db_path: str = "app/data/events.db"
    database_url: str = ""

    # Redis (ARQ job queue + API cache)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "FIM_REDIS_URL"),
    )

    # Scheduler
    scheduler_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("SCHEDULER_ENABLED", "FIM_SCHEDULER_ENABLED"),
    )
    scheduler_interval_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices("SCHEDULER_INTERVAL_MINUTES", "FIM_SCHEDULER_INTERVAL_MINUTES"),
    )

    # Cache TTL (seconds)
    cache_heatmap_ttl: int = 30
    cache_timeline_ttl: int = 15


settings = Settings()
