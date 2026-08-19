from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

from app.bot.client import ZorysaBot


def test_bot_uses_only_the_guilds_intent() -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")

    assert bot.intents.value == discord.Intents(guilds=True).value


@pytest.mark.parametrize("guild_id", [None, 123456789])
async def test_setup_registers_health_and_syncs_commands(guild_id: int | None) -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot", guild_id=guild_id)
    bot.tree.sync = AsyncMock()
    bot.tree.copy_global_to = MagicMock()

    await bot.setup_hook()

    assert bot.tree.get_command("health") is not None
    if guild_id is None:
        bot.tree.copy_global_to.assert_not_called()
        bot.tree.sync.assert_awaited_once_with()
    else:
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to.assert_called_once_with(guild=guild)
        bot.tree.sync.assert_awaited_once_with(guild=guild)


async def test_health_reports_bot_name_latency_and_current_guild() -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")
    command = bot.tree.get_command("health")
    interaction = MagicMock()
    interaction.guild.name = "LACIS"
    interaction.response.send_message = AsyncMock()

    assert command is not None
    with patch.object(ZorysaBot, "latency", new_callable=PropertyMock, return_value=0.042):
        await command.callback(interaction)

    interaction.response.send_message.assert_awaited_once()
    content = interaction.response.send_message.await_args.args[0]
    assert "Zorysa Daily Bot" in content
    assert "42 ms" in content
    assert "LACIS" in content
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True
