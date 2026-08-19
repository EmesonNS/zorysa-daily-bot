from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.commands.daily import build_daily_group
from app.bot.contracts import OpenedDaily
from tests.unit.bot.test_daily_presentation import _panel


def _interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = 123
    interaction.guild = SimpleNamespace(id=123, name="LACIS", owner_id=10)
    interaction.user = SimpleNamespace(id=10, roles=[])
    interaction.permissions.manage_guild = True
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _open_command(group: app_commands.Group) -> app_commands.Command:
    command = group.get_command("abrir")
    assert isinstance(command, app_commands.Command)
    return command


async def test_open_daily_publishes_panel_and_attaches_message_id() -> None:
    service = MagicMock()
    service.open_daily = AsyncMock(
        return_value=OpenedDaily(panel=_panel(), channel_id=55, message_id=None)
    )
    service.attach_message = AsyncMock()
    public_message = SimpleNamespace(id=999)
    channel = SimpleNamespace(send=AsyncMock(return_value=public_message))
    bot = MagicMock()
    bot.get_channel.return_value = channel
    interaction = _interaction()

    await _open_command(build_daily_group(bot, service)).callback(interaction, "amazhealth")

    channel.send.assert_awaited_once()
    kwargs = channel.send.await_args.kwargs
    assert kwargs["embed"].title == "Daily • AmazHealth"
    assert kwargs["view"].timeout is None
    service.attach_message.assert_awaited_once_with(session_id=7, message_id=999)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)


async def test_open_daily_does_not_duplicate_existing_message() -> None:
    service = MagicMock()
    service.open_daily = AsyncMock(
        return_value=OpenedDaily(panel=_panel(), channel_id=55, message_id=999)
    )
    service.attach_message = AsyncMock()
    bot = MagicMock()
    interaction = _interaction()

    await _open_command(build_daily_group(bot, service)).callback(interaction, "amazhealth")

    bot.get_channel.assert_not_called()
    service.attach_message.assert_not_awaited()
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "já está aberta" in content
