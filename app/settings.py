"""Environment-backed application settings."""

from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated configuration loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "Zorysa Daily Bot"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    timezone: str = "America/Belem"

    discord_token: SecretStr
    discord_guild_id: int | None = None
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql(cls, value: SecretStr) -> SecretStr:
        """Restrict runtime connections to the configured async PostgreSQL driver."""

        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        return value

    @property
    def secrets_for_logging(self) -> tuple[str, ...]:
        """Return sensitive values that the logging layer must redact."""

        return (
            self.discord_token.get_secret_value(),
            self.database_url.get_secret_value(),
        )
