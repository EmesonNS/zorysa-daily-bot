from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import discord
import pytest

from app.bot.client import ZorysaBot


def test_bot_uses_only_guilds_and_members_intents() -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")

    assert bot.intents.value == discord.Intents(guilds=True, members=True).value


def test_bot_keeps_presence_and_message_content_intents_disabled() -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")

    assert bot.intents.presences is False
    assert bot.intents.message_content is False


async def test_raw_member_remove_delegates_guild_and_user_ids() -> None:
    service = MagicMock(leave_guild=AsyncMock(return_value=2))
    bot = ZorysaBot(app_name="Zorysa Daily Bot", member_lifecycle_service=service)
    payload = MagicMock(guild_id=123)
    payload.user.id = 77

    await bot.on_raw_member_remove(payload)

    service.leave_guild.assert_awaited_once_with(123, 77)


async def test_raw_member_remove_is_a_noop_without_bound_service() -> None:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")
    payload = MagicMock(guild_id=123)
    payload.user.id = 77

    await bot.on_raw_member_remove(payload)


async def test_raw_member_remove_isolates_service_failure(caplog: pytest.LogCaptureFixture) -> None:
    service = MagicMock(leave_guild=AsyncMock(side_effect=RuntimeError("private")))
    bot = ZorysaBot(app_name="Zorysa Daily Bot", member_lifecycle_service=service)
    payload = MagicMock(guild_id=123)
    payload.user.id = 77

    await bot.on_raw_member_remove(payload)

    assert "guild 123" in caplog.text and "user 77" in caplog.text
    assert "private" not in caplog.text


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


async def test_bot_delegates_scheduler_lifecycle_and_closes_it_first() -> None:
    lifecycle = MagicMock()
    lifecycle.setup = AsyncMock()
    lifecycle.ready = AsyncMock()
    lifecycle.disconnect = AsyncMock()
    lifecycle.shutdown = AsyncMock()
    bot = ZorysaBot(app_name="Zorysa Daily Bot", automation_lifecycle=lifecycle)
    bot.tree.sync = AsyncMock()

    await bot.setup_hook()
    await bot.on_ready()
    await bot.on_disconnect()
    parent_close = AsyncMock()
    with patch("discord.ext.commands.Bot.close", parent_close):
        manager = MagicMock()
        manager.attach_mock(lifecycle.shutdown, "scheduler")
        manager.attach_mock(parent_close, "discord")
        await bot.close()
        assert manager.mock_calls == [call.scheduler(), call.discord()]

    lifecycle.setup.assert_awaited_once_with()
    lifecycle.ready.assert_awaited_once_with()
    lifecycle.disconnect.assert_awaited_once_with()


async def test_bot_restores_scheduler_when_discord_session_resumes() -> None:
    lifecycle = MagicMock()
    lifecycle.ready = AsyncMock()
    bot = ZorysaBot(app_name="Zorysa Daily Bot", automation_lifecycle=lifecycle)

    await bot.on_resumed()

    lifecycle.ready.assert_awaited_once_with()
