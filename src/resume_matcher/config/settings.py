from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return value


CsvTuple = Annotated[tuple[str, ...], NoDecode, BeforeValidator(_split_csv)]


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class AIProvider(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_name: str = "AI Resume & Job Match Agent"
    app_version: str = "0.1.0"
    app_debug: bool = False
    app_api_keys: CsvTuple = ()
    app_allowed_hosts: CsvTuple = ("localhost", "127.0.0.1", "testserver")
    app_cors_origins: CsvTuple = ()
    app_max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    app_max_job_description_chars: int = Field(default=50_000, ge=500, le=200_000)
    app_data_retention_days: int = Field(default=30, ge=1, le=365)
    app_rate_limit_per_minute: int = Field(default=30, ge=1, le=10_000)

    ai_provider: AIProvider = AIProvider.LOCAL
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-luna"
    openai_timeout_seconds: float = Field(default=45.0, ge=5, le=180)
    openai_max_retries: int = Field(default=3, ge=0, le=8)
    openai_max_output_tokens: int = Field(default=16_000, ge=1_024, le=128_000)

    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./data/resume_matcher.db")
    database_echo: bool = False
    database_auto_create_schema: bool = True
    storage_path: Path = Path("./data/uploads")

    log_level: str = "INFO"
    log_json: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnvironment.PRODUCTION

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @model_validator(mode="after")
    def validate_secure_production_configuration(self) -> Settings:
        if self.is_production:
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in production")
            if not self.app_api_keys:
                raise ValueError("APP_API_KEYS must contain at least one key in production")
            if "*" in self.app_allowed_hosts:
                raise ValueError("Wildcard hosts are not allowed in production")
            if self.ai_provider is AIProvider.OPENAI and self.openai_api_key is None:
                raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
            if self.database_auto_create_schema:
                raise ValueError(
                    "DATABASE_AUTO_CREATE_SCHEMA must be false in production; apply Alembic "
                    "migrations before startup"
                )
        return self
