import asyncio
import os

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _read_applied_revisions(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            return list(result.scalars())
    finally:
        await engine.dispose()


async def _seed_pre_automatic_daily_schema(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM guilds WHERE discord_guild_id = 987654321012345678")
            )
            guild_id = await connection.scalar(
                text(
                    "INSERT INTO guilds (discord_guild_id, name) "
                    "VALUES (987654321012345678, 'Migration Guild') RETURNING id"
                )
            )
            await connection.execute(
                text("INSERT INTO guild_settings (guild_id) VALUES (:guild_id)"),
                {"guild_id": guild_id},
            )
    finally:
        await engine.dispose()


async def _assert_automatic_daily_upgrade(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            settings = (
                await connection.execute(
                    text(
                        "SELECT daily_enabled, daily_open_time, first_reminder_time, "
                        "last_reminder_time, daily_close_time FROM guild_settings gs "
                        "JOIN guilds g ON g.id = gs.guild_id "
                        "WHERE g.discord_guild_id = 987654321012345678"
                    )
                )
            ).one()
            assert tuple(str(value) for value in settings) == (
                "True",
                "09:00:00",
                "10:30:00",
                "11:30:00",
                "12:00:00",
            )
            weekdays = (
                await connection.execute(
                    text(
                        "SELECT ged.weekday FROM guild_execution_days ged "
                        "JOIN guilds g ON g.id = ged.guild_id "
                        "WHERE g.discord_guild_id = 987654321012345678 "
                        "ORDER BY ged.weekday"
                    )
                )
            ).scalars()
            assert list(weekdays) == [0, 1, 2, 3, 4]
    finally:
        await engine.dispose()


async def _seed_automatic_daily_state(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            guild_id = await connection.scalar(
                text("SELECT id FROM guilds WHERE discord_guild_id = 987654321012345678")
            )
            project_id = await connection.scalar(
                text(
                    "INSERT INTO projects "
                    "(guild_id, name, slug, discord_channel_id) "
                    "VALUES (:guild_id, 'Migration Project', 'migration-project', "
                    "876543210123456789) RETURNING id"
                ),
                {"guild_id": guild_id},
            )
            session_id = await connection.scalar(
                text(
                    "INSERT INTO daily_sessions (project_id, session_date) "
                    "VALUES (:project_id, DATE '2026-08-19') RETURNING id"
                ),
                {"project_id": project_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO daily_assignments "
                    "(session_id, discord_user_id, display_name, status) "
                    "VALUES (:session_id, 765432101234567890, 'Migration User', "
                    "'NOT_ANSWERED')"
                ),
                {"session_id": session_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO daily_notifications (session_id, kind) "
                    "VALUES (:session_id, 'FIRST_REMINDER')"
                ),
                {"session_id": session_id},
            )
    finally:
        await engine.dispose()


async def _assert_automatic_daily_downgrade(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name IN "
                        "('guild_execution_days', 'daily_notifications')"
                    )
                )
            ).scalars()
            assert list(tables) == []
            columns = (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'guild_settings' "
                        "AND column_name LIKE '%daily%'"
                    )
                )
            ).scalars()
            assert list(columns) == []
            assignment_status = await connection.scalar(
                text(
                    "SELECT status FROM daily_assignments "
                    "WHERE discord_user_id = 765432101234567890"
                )
            )
            assert assignment_status == "PENDING"
    finally:
        await engine.dispose()


def test_upgrade_head_is_idempotent_and_records_revision() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    head_revision = ScriptDirectory.from_config(config).get_current_head()
    assert head_revision is not None
    assert asyncio.run(_read_applied_revisions(database_url)) == [head_revision]


def test_automatic_daily_migration_upgrades_downgrades_and_reupgrades() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "0002_manual_daily")
    asyncio.run(_seed_pre_automatic_daily_schema(database_url))

    command.upgrade(config, "head")
    asyncio.run(_assert_automatic_daily_upgrade(database_url))
    asyncio.run(_seed_automatic_daily_state(database_url))

    command.downgrade(config, "0002_manual_daily")
    asyncio.run(_assert_automatic_daily_downgrade(database_url))

    command.upgrade(config, "head")
    asyncio.run(_assert_automatic_daily_upgrade(database_url))
