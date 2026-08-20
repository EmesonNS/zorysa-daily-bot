"""Application entry point and dependency composition."""

import asyncio
import logging
from datetime import UTC
from typing import cast

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.application.automatic_daily import AutomaticDailyService
from app.application.daily import DailyService
from app.application.guild_admin import GuildAdminService
from app.application.projects import ProjectService
from app.application.questions import QuestionService
from app.application.schedule import ScheduleService
from app.bot.client import ZorysaBot
from app.infrastructure.database import Database, DatabaseUnavailableError
from app.infrastructure.discord import DiscordDailyGateway
from app.infrastructure.scheduler.coordinator import (
    DatabaseScheduleSource,
    SchedulerAdapter,
    SchedulerCoordinator,
)
from app.infrastructure.scheduler.lifecycle import (
    LifecycleScheduler,
    SchedulerLifecycle,
)
from app.logging import configure_logging
from app.settings import Settings

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    """Validate dependencies and run the Discord client until shutdown."""

    database = Database(settings)
    try:
        await database.check_readiness()
        logger.info("Database readiness check passed")

        daily_service = DailyService(database.sessions, timezone=settings.timezone)
        automatic_service = AutomaticDailyService(database.sessions)
        schedule_service = ScheduleService(database.sessions, timezone=settings.timezone)
        bot = ZorysaBot(
            app_name=settings.app_name,
            guild_id=settings.discord_guild_id,
            guild_admin_service=GuildAdminService(database.sessions, timezone=settings.timezone),
            schedule_service=schedule_service,
            question_service=QuestionService(database.sessions, timezone=settings.timezone),
            project_service=ProjectService(database.sessions, timezone=settings.timezone),
            daily_service=daily_service,
        )
        scheduler = AsyncIOScheduler(timezone=UTC)
        coordinator = SchedulerCoordinator(
            scheduler=cast(SchedulerAdapter, scheduler),
            schedule_source=DatabaseScheduleSource(database.sessions),
            automatic_service=automatic_service,
            gateway=DiscordDailyGateway(bot, daily_service, automatic_service),
        )
        schedule_service.bind_reloader(coordinator)
        bot.bind_automation_lifecycle(
            SchedulerLifecycle(
                cast(LifecycleScheduler, scheduler),
                coordinator,
            )
        )
        try:
            logger.info("Starting %s", settings.app_name)
            await bot.start(settings.discord_token.get_secret_value(), reconnect=True)
        finally:
            await bot.close()
    finally:
        await database.engine.dispose()


def main() -> None:
    """Load settings, configure logging, and start the application."""

    try:
        settings = Settings()  # type: ignore[call-arg]  # Loaded from environment.
    except ValidationError as error:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(__name__).error(
            "Invalid application configuration; check required environment variables"
        )
        raise SystemExit(1) from error

    configure_logging(level=settings.log_level, secrets=settings.secrets_for_logging)

    try:
        asyncio.run(run(settings))
    except DatabaseUnavailableError as error:
        logger.error("Application startup failed: database is unavailable")
        raise SystemExit(1) from error
    except discord.LoginFailure as error:
        logger.error("Application startup failed: Discord authentication was rejected")
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        logger.info("Application shutdown requested")


if __name__ == "__main__":
    main()
