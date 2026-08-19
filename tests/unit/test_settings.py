import logging

import pytest
from pydantic import ValidationError

from app.logging import configure_logging
from app.settings import Settings


def test_settings_load_required_values_and_safe_defaults() -> None:
    settings = Settings(
        discord_token="super-secret-token",
        database_url="postgresql+asyncpg://user:password@db:5432/zorysa",
        _env_file=None,
    )

    assert settings.app_name == "Zorysa Daily Bot"
    assert settings.timezone == "America/Belem"
    assert settings.log_level == "INFO"
    assert "super-secret-token" not in repr(settings)


def test_settings_reject_missing_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as token_error:
        Settings(
            database_url="postgresql+asyncpg://user:password@db:5432/zorysa",
            _env_file=None,
        )
    assert "discord_token" in str(token_error.value)

    with pytest.raises(ValidationError) as database_error:
        Settings(discord_token="token", _env_file=None)
    assert "database_url" in str(database_error.value)


def test_settings_reject_non_async_postgresql_url() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(
            discord_token="token",
            database_url="postgresql://user:password@db:5432/zorysa",
            _env_file=None,
        )


def test_logging_redacts_registered_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", secrets=("super-secret-token", "password"))

    logging.getLogger("zorysa.test").info(
        "authentication failed token=%s database_password=%s",
        "super-secret-token",
        "password",
    )

    output = capsys.readouterr().err
    assert "super-secret-token" not in output
    assert "password" not in output
    assert "[REDACTED]" in output
