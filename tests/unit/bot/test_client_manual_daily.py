from unittest.mock import AsyncMock, MagicMock

from app.bot.client import ZorysaBot
from app.bot.views.daily import DailyResponseView


def _bot() -> ZorysaBot:
    return ZorysaBot(
        app_name="Zorysa Daily Bot",
        guild_admin_service=MagicMock(),
        schedule_service=MagicMock(),
        project_service=MagicMock(),
        daily_service=MagicMock(),
    )


def test_manual_daily_command_groups_are_registered_together() -> None:
    bot = _bot()

    assert bot.tree.get_command("config") is not None
    assert bot.tree.get_command("projeto") is not None
    assert bot.tree.get_command("daily") is not None
    assert bot.tree.get_command("health") is not None


def test_partial_manual_daily_dependencies_are_rejected() -> None:
    try:
        ZorysaBot(app_name="Zorysa Daily Bot", guild_admin_service=MagicMock())
    except ValueError as error:
        assert "services" in str(error)
    else:
        raise AssertionError("partial service composition should fail")


async def test_setup_registers_persistent_daily_view_before_sync() -> None:
    bot = _bot()
    bot.tree.sync = AsyncMock()
    bot.add_view = MagicMock()

    await bot.setup_hook()

    view = bot.add_view.call_args.args[0]
    assert isinstance(view, DailyResponseView)
    assert view.timeout is None
    bot.tree.sync.assert_awaited_once_with()
