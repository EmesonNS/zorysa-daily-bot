import asyncio
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

GUILD_ID = 987654321012345679
USER_ID = 765432101234567891


async def _seed_pre_m3(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM guilds WHERE discord_guild_id = :guild_id"),
                {"guild_id": GUILD_ID},
            )
            guild_id = await connection.scalar(
                text(
                    "INSERT INTO guilds (discord_guild_id, name) "
                    "VALUES (:guild_id, 'M3 Migration Guild') RETURNING id"
                ),
                {"guild_id": GUILD_ID},
            )
            await connection.execute(
                text("INSERT INTO guild_settings (guild_id) VALUES (:guild_id)"),
                {"guild_id": guild_id},
            )
            project_id = await connection.scalar(
                text(
                    "INSERT INTO projects (guild_id, name, slug, discord_channel_id) "
                    "VALUES (:guild_id, 'M3 Migration', 'm3-migration', 876543210123456780) "
                    "RETURNING id"
                ),
                {"guild_id": guild_id},
            )
            session_id = await connection.scalar(
                text(
                    "INSERT INTO daily_sessions (project_id, session_date) "
                    "VALUES (:project_id, DATE '2026-08-20') RETURNING id"
                ),
                {"project_id": project_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO daily_assignments "
                    "(session_id, discord_user_id, display_name, status) "
                    "VALUES (:session_id, :user_id, 'M3 User', 'NOT_ANSWERED')"
                ),
                {"session_id": session_id, "user_id": USER_ID},
            )
    finally:
        await engine.dispose()


async def _exercise_and_assert_upgrade(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            guild_id = await connection.scalar(
                text("SELECT id FROM guilds WHERE discord_guild_id = :guild_id"),
                {"guild_id": GUILD_ID},
            )
            report_time = await connection.scalar(
                text("SELECT daily_report_time FROM guild_settings WHERE guild_id = :guild_id"),
                {"guild_id": guild_id},
            )
            assert str(report_time) == "12:10:00"

            await connection.execute(
                text(
                    "UPDATE daily_assignments SET status = 'EXCUSED', excused_at = now(), "
                    "excused_by_user_id = 123456789012345678, excuse_reason = 'Treinamento' "
                    "WHERE discord_user_id = :user_id"
                ),
                {"user_id": USER_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO report_channels "
                    "(guild_id, discord_channel_id) VALUES (:guild_id, 876543210123456781)"
                ),
                {"guild_id": guild_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO daily_report_deliveries "
                    "(guild_id, report_date, discord_channel_id) "
                    "VALUES (:guild_id, DATE '2026-08-20', 876543210123456781)"
                ),
                {"guild_id": guild_id},
            )
    finally:
        await engine.dispose()


async def _assert_downgrade(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = (
                await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name IN "
                        "('report_channels', 'daily_report_deliveries')"
                    )
                )
            ).scalars()
            assert list(tables) == []
            columns = (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND "
                        "((table_name = 'guild_settings' AND column_name = 'daily_report_time') "
                        "OR (table_name = 'daily_assignments' AND column_name LIKE 'excuse%'))"
                    )
                )
            ).scalars()
            assert list(columns) == []
            status = await connection.scalar(
                text("SELECT status FROM daily_assignments WHERE discord_user_id = :user_id"),
                {"user_id": USER_ID},
            )
            assert status == "NOT_ANSWERED"
    finally:
        await engine.dispose()


def test_daily_management_migration_upgrades_downgrades_and_reupgrades() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "0003_automatic_daily")
    asyncio.run(_seed_pre_m3(database_url))

    command.upgrade(config, "head")
    asyncio.run(_exercise_and_assert_upgrade(database_url))

    command.downgrade(config, "0003_automatic_daily")
    asyncio.run(_assert_downgrade(database_url))

    command.upgrade(config, "head")
