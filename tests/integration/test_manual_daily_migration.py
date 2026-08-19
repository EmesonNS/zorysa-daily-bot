import asyncio
import os
from collections.abc import Collection

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_TABLES = {
    "admin_roles",
    "daily_answers",
    "daily_assignments",
    "daily_question_snapshots",
    "daily_questions",
    "daily_sessions",
    "guild_settings",
    "guilds",
    "project_memberships",
    "projects",
}


async def _table_names(database_url: str) -> Collection[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
    finally:
        await engine.dispose()


def test_manual_daily_migration_supports_upgrade_downgrade_and_reupgrade() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= set(asyncio.run(_table_names(database_url)))

    try:
        command.downgrade(config, "0001_baseline")
        assert EXPECTED_TABLES.isdisjoint(asyncio.run(_table_names(database_url)))
    finally:
        command.upgrade(config, "head")

    assert EXPECTED_TABLES <= set(asyncio.run(_table_names(database_url)))
