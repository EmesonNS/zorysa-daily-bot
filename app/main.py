"""Application entry point and dependency composition."""

import asyncio
import logging

import discord
from pydantic import ValidationError

from app.bot.client import ZorysaBot
from app.infrastructure.database import Database, DatabaseUnavailableError
from app.logging import configure_logging
from app.settings import Settings

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    """Validate dependencies and run the Discord client until shutdown."""

    database = Database(settings)
    try:
        await database.check_readiness()
        logger.info("Database readiness check passed")

        bot = ZorysaBot(app_name=settings.app_name, guild_id=settings.discord_guild_id)
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
