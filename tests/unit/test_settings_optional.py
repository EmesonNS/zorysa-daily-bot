from app.settings import Settings


def test_empty_optional_guild_id_is_ignored(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DISCORD_TOKEN", "token-for-test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/test")
    monkeypatch.setenv("DISCORD_GUILD_ID", "")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.discord_guild_id is None
