"""SQLAlchemy async engine, sessions, and readiness checks."""

from typing import Self

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings import Settings


class DatabaseUnavailableError(RuntimeError):
    """Report a database outage without leaking connection details."""


class Database:
    """Own the application's async SQLAlchemy resources."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    def __init__(self, settings: Settings) -> None:
        """Create database resources from validated application settings."""

        self.engine = create_async_engine(settings.database_url.get_secret_value())
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @classmethod
    def from_engine(cls, engine: AsyncEngine) -> Self:
        """Create database resources around an existing engine."""

        database = cls.__new__(cls)
        database.engine = engine
        database.sessions = async_sessionmaker(engine, expire_on_commit=False)
        return database

    async def check_readiness(self) -> None:
        """Verify connectivity with a minimal query."""

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise DatabaseUnavailableError(
                "Database readiness check failed: database is unavailable"
            ) from error
