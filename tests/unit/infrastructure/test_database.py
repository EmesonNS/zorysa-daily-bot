from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.infrastructure.database import Database, DatabaseUnavailableError
from app.settings import Settings


def test_database_creates_async_engine_and_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    session_factory = MagicMock()
    create_async_engine = MagicMock(return_value=engine)
    async_sessionmaker = MagicMock(return_value=session_factory)
    monkeypatch.setattr("app.infrastructure.database.core.create_async_engine", create_async_engine)
    monkeypatch.setattr("app.infrastructure.database.core.async_sessionmaker", async_sessionmaker)
    settings = Settings(
        discord_token="token",
        database_url="postgresql+asyncpg://user:password@db:5432/zorysa",
        _env_file=None,
    )

    database = Database(settings)

    create_async_engine.assert_called_once_with("postgresql+asyncpg://user:password@db:5432/zorysa")
    async_sessionmaker.assert_called_once_with(engine, expire_on_commit=False)
    assert database.engine is engine
    assert database.sessions is session_factory


async def test_database_readiness_executes_select_one() -> None:
    connection = AsyncMock()
    connection_context = AsyncMock()
    connection_context.__aenter__.return_value = connection
    engine = MagicMock()
    engine.connect.return_value = connection_context
    database = Database.from_engine(engine)

    await database.check_readiness()

    statement = connection.execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


async def test_database_readiness_raises_sanitized_operational_error() -> None:
    database_url = "postgresql+asyncpg://user:password@db:5432/zorysa"
    connection_context = AsyncMock()
    connection_context.__aenter__.side_effect = OperationalError(
        "SELECT 1",
        {},
        ConnectionError(f"connection refused for {database_url}"),
    )
    engine = MagicMock()
    engine.connect.return_value = connection_context
    database = Database.from_engine(engine)

    with pytest.raises(DatabaseUnavailableError) as error:
        await database.check_readiness()

    message = str(error.value)
    assert message == "Database readiness check failed: database is unavailable"
    assert database_url not in message
    assert "password" not in message
