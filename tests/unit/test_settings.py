from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from resume_matcher.config.settings import AIProvider, AppEnvironment, Settings


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep settings tests deterministic under CI and developer shell configuration."""
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)
        monkeypatch.delenv(field_name.lower(), raising=False)


def test_development_defaults_are_safe_and_documentation_is_enabled() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.app_debug is False
    assert settings.ai_provider is AIProvider.LOCAL
    assert settings.app_api_keys == ()
    assert "*" not in settings.app_allowed_hosts
    assert settings.docs_enabled is True
    assert settings.is_production is False
    assert settings.storage_path == Path("data/uploads")


def test_csv_settings_strip_empty_values_and_preserve_order() -> None:
    settings = Settings(
        _env_file=None,
        app_api_keys=" key-one, ,key-two ",
        app_allowed_hosts="api.example.com, admin.example.com",
        app_cors_origins="https://app.example.com,",
    )

    assert settings.app_api_keys == ("key-one", "key-two")
    assert settings.app_allowed_hosts == ("api.example.com", "admin.example.com")
    assert settings.app_cors_origins == ("https://app.example.com",)


def test_settings_read_case_insensitive_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("app_env", "test")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "42")
    monkeypatch.setenv("APP_API_KEYS", "key-one,key-two")
    monkeypatch.setenv("APP_ALLOWED_HOSTS", "api.example.com,admin.example.com")

    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnvironment.TEST
    assert settings.app_rate_limit_per_minute == 42
    assert settings.app_api_keys == ("key-one", "key-two")
    assert settings.app_allowed_hosts == ("api.example.com", "admin.example.com")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "app_debug": True,
                "app_api_keys": ("secret",),
                "app_allowed_hosts": ("api.example.com",),
            },
            "APP_DEBUG must be false",
        ),
        (
            {"app_allowed_hosts": ("api.example.com",)},
            "APP_API_KEYS must contain at least one key",
        ),
        (
            {"app_api_keys": ("secret",), "app_allowed_hosts": ("*",)},
            "Wildcard hosts are not allowed",
        ),
        (
            {
                "app_api_keys": ("secret",),
                "app_allowed_hosts": ("api.example.com",),
                "ai_provider": "openai",
            },
            "OPENAI_API_KEY is required",
        ),
    ],
)
def test_production_rejects_insecure_configuration(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, app_env="production", **overrides)


def test_valid_production_configuration_disables_docs_and_redacts_secrets() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_api_keys="client-key",
        app_allowed_hosts="api.example.com",
        ai_provider="openai",
        openai_api_key="openai-secret-value",
        database_url="postgresql+asyncpg://user:password@example.com/resumes",
    )

    assert settings.is_production is True
    assert settings.docs_enabled is False
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "openai-secret-value"
    assert "openai-secret-value" not in repr(settings)
    assert "password@example.com" not in repr(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_max_upload_bytes", 1023),
        ("app_max_job_description_chars", 499),
        ("app_data_retention_days", 0),
        ("app_rate_limit_per_minute", 0),
        ("openai_timeout_seconds", 4.9),
        ("openai_max_retries", 9),
    ],
)
def test_operational_limits_are_validated(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
