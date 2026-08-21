import asyncio
import os
from datetime import date, time

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

GUILD_ID = 987654321012345680
CHANNEL_ID = 876543210123456782
ACTOR_ID = 765432101234567892


async def _seed_pre_m4(database_url: str) -> None:
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
                    "VALUES (:guild_id, 'M4 Migration Guild') RETURNING id"
                ),
                {"guild_id": GUILD_ID},
            )
            await connection.execute(
                text("INSERT INTO guild_settings (guild_id) VALUES (:guild_id)"),
                {"guild_id": guild_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO daily_report_deliveries "
                    "(guild_id, report_date, discord_channel_id, page_count) "
                    "VALUES (:guild_id, DATE '2026-08-21', :channel_id, 2)"
                ),
                {"guild_id": guild_id, "channel_id": CHANNEL_ID},
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
            settings = (
                await connection.execute(
                    text(
                        "SELECT weekly_report_weekday, weekly_report_time, monthly_report_time "
                        "FROM guild_settings WHERE guild_id = :guild_id"
                    ),
                    {"guild_id": guild_id},
                )
            ).one()
            assert settings == (4, time(12, 20), time(12, 20))

            delivery = (
                await connection.execute(
                    text(
                        "SELECT kind, period_start, period_end, page_count "
                        "FROM report_deliveries WHERE guild_id = :guild_id"
                    ),
                    {"guild_id": guild_id},
                )
            ).one()
            assert delivery == (
                "DAILY",
                date(2026, 8, 21),
                date(2026, 8, 21),
                2,
            )

            await connection.execute(
                text(
                    "INSERT INTO report_deliveries "
                    "(guild_id, kind, period_start, period_end, discord_channel_id) "
                    "VALUES (:guild_id, 'WEEKLY', DATE '2026-08-17', "
                    "DATE '2026-08-21', :channel_id)"
                ),
                {"guild_id": guild_id, "channel_id": CHANNEL_ID},
            )
            await connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(guild_id, actor_user_id, action, target_type, target_id, details) "
                    "VALUES (:guild_id, :actor_id, 'PROJECT_CREATED', "
                    "'project', 42, '{\"name\": \"M4\"}'::jsonb)"
                ),
                {"guild_id": guild_id, "actor_id": ACTOR_ID},
            )

            constraint_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint "
                            "WHERE conrelid IN "
                            "('guild_settings'::regclass, 'report_deliveries'::regclass)"
                        )
                    )
                ).scalars()
            )
            assert {
                "ck_guild_settings_valid_weekly_report_weekday",
                "ck_report_deliveries_report_kind",
                "ck_report_deliveries_valid_period",
                "uq_report_deliveries_guild_kind_period_channel",
            }.issubset(constraint_names)

            index_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
                            "AND tablename = 'audit_events'"
                        )
                    )
                ).scalars()
            )
            assert {
                "ix_audit_events_guild_occurred_id",
                "ix_audit_events_guild_actor",
                "ix_audit_events_guild_action",
            }.issubset(index_names)
    finally:
        await engine.dispose()


async def _assert_downgrade(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_name IN "
                            "('daily_report_deliveries', 'report_deliveries', 'audit_events')"
                        )
                    )
                ).scalars()
            )
            assert tables == {"daily_report_deliveries"}

            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'guild_settings' "
                            "AND column_name IN ('weekly_report_weekday', "
                            "'weekly_report_time', 'monthly_report_time')"
                        )
                    )
                ).scalars()
            )
            assert columns == set()

            guild_id = await connection.scalar(
                text("SELECT id FROM guilds WHERE discord_guild_id = :guild_id"),
                {"guild_id": GUILD_ID},
            )
            deliveries = (
                await connection.execute(
                    text(
                        "SELECT report_date, discord_channel_id, page_count "
                        "FROM daily_report_deliveries WHERE guild_id = :guild_id"
                    ),
                    {"guild_id": guild_id},
                )
            ).all()
            assert deliveries == [(date(2026, 8, 21), CHANNEL_ID, 2)]
    finally:
        await engine.dispose()


def test_historical_management_migration_round_trip_preserves_daily_reports() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "0004_daily_management")
    asyncio.run(_seed_pre_m4(database_url))

    command.upgrade(config, "head")
    asyncio.run(_exercise_and_assert_upgrade(database_url))

    command.downgrade(config, "0004_daily_management")
    asyncio.run(_assert_downgrade(database_url))

    command.upgrade(config, "head")


def test_historical_management_upgrade_head_is_idempotent() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    asyncio.run(_exercise_and_assert_upgrade(database_url))
