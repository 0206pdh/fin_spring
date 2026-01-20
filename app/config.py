from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="fim_", env_file=".env", extra="ignore")

    # RapidAPI
    rapidapi_key: str = ""
    rapidapi_host: str = ""
    rapidapi_base_url: str = ""
    rapidapi_timeout_sec: int = 20
    rapidapi_details_timeout_sec: int = 25

    # Local LLM (OpenAI-compatible)
    llm_provider: str = Field(default="local", validation_alias=AliasChoices("LLM_PROVIDER", "FIM_LLM_PROVIDER"))
    llm_base_url: str = Field(
        default="http://localhost:8000/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "FIM_LLM_BASE_URL"),
    )
    llm_model: str = Field(default="mistral", validation_alias=AliasChoices("LLM_MODEL", "FIM_LLM_MODEL"))
    llm_timeout_sec: int = 30
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY", "FIM_OPENAI_API_KEY"))
    openai_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("OPENAI_MODEL", "FIM_OPENAI_MODEL"))
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "FIM_OPENAI_BASE_URL"),
    )

    # Logging
    log_level: str = "INFO"

    # Storage
    db_path: str = "app/data/events.db"
    database_url: str = ""

    # Ingestion endpoints. Override with JSON string in FIM_RAPIDAPI_ENDPOINTS.
    rapidapi_endpoints_json: str = ""


settings = Settings()
