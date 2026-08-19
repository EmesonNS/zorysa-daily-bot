from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.commands.config import build_config_group
from app.bot.contracts import AdminRoleSummary, ScheduleSummary


def _interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = 123
    interaction.guild = SimpleNamespace(id=123, name="LACIS", owner_id=10)
    interaction.user = SimpleNamespace(
        id=10,
        roles=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
    )
    interaction.permissions.manage_guild = True
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _admin_command(group: app_commands.Group, name: str) -> app_commands.Command:
    admin = group.get_command("admin")
    assert isinstance(admin, app_commands.Group)
    command = admin.get_command(name)
    assert isinstance(command, app_commands.Command)
    return command


def _agenda_command(group: app_commands.Group, name: str) -> app_commands.Command:
    agenda = group.get_command("agenda")
    assert isinstance(agenda, app_commands.Group)
    command = agenda.get_command(name)
    assert isinstance(command, app_commands.Command)
    return command


def _schedule() -> ScheduleSummary:
    return ScheduleSummary(
        timezone="America/Belem",
        daily_enabled=True,
        execution_days=(0, 1, 2, 3, 4),
        opening=time(9),
        first_reminder=time(10, 30),
        last_reminder=time(11, 30),
        closing=time(12),
    )


async def test_add_admin_role_passes_actor_context_and_replies_ephemerally() -> None:
    service = MagicMock()
    service.add_admin_role = AsyncMock()
    interaction = _interaction()
    role = SimpleNamespace(id=88, name="Gestores")

    await _admin_command(build_config_group(service), "role-adicionar").callback(interaction, role)

    actor = service.add_admin_role.await_args.kwargs["actor"]
    assert actor.guild_id == 123
    assert actor.user_id == 10
    assert actor.role_ids == (1, 2)
    assert actor.is_guild_owner is True
    assert actor.can_manage_guild is True
    assert service.add_admin_role.await_args.kwargs["role_id"] == 88
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert "Gestores" in interaction.edit_original_response.await_args.kwargs["content"]


async def test_remove_admin_role_invokes_service() -> None:
    service = MagicMock()
    service.remove_admin_role = AsyncMock()
    interaction = _interaction()
    role = SimpleNamespace(id=88, name="Gestores")

    await _admin_command(build_config_group(service), "role-remover").callback(interaction, role)

    service.remove_admin_role.assert_awaited_once()
    assert service.remove_admin_role.await_args.kwargs["role_id"] == 88


async def test_list_admin_roles_formats_mentions() -> None:
    service = MagicMock()
    service.list_admin_roles = AsyncMock(
        return_value=(AdminRoleSummary(role_id=88), AdminRoleSummary(role_id=99))
    )
    interaction = _interaction()

    command = _admin_command(build_config_group(service), "roles")
    assert command.description == "Lista os cargos com acesso administrativo"
    await command.callback(interaction)

    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "Cargos com acesso administrativo ao bot:" in content
    assert "<@&88>" in content
    assert "<@&99>" in content


async def test_view_schedule_formats_days_times_and_timezone_ephemerally() -> None:
    admin_service = MagicMock()
    schedule_service = MagicMock()
    schedule_service.get_schedule = AsyncMock(return_value=_schedule())
    interaction = _interaction()

    command = _agenda_command(build_config_group(admin_service, schedule_service), "visualizar")
    await command.callback(interaction)

    schedule_service.get_schedule.assert_awaited_once()
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "America/Belem" in content
    assert "Segunda" in content and "Sexta" in content
    assert "09:00" in content and "12:00" in content


async def test_update_schedule_times_passes_all_values() -> None:
    admin_service = MagicMock()
    schedule_service = MagicMock()
    schedule_service.update_times = AsyncMock(return_value=_schedule())
    interaction = _interaction()

    command = _agenda_command(build_config_group(admin_service, schedule_service), "horarios")
    await command.callback(interaction, "08:00", "09:00", "10:00", "11:00")

    assert schedule_service.update_times.await_args.kwargs == {
        "actor": schedule_service.update_times.await_args.kwargs["actor"],
        "opening": "08:00",
        "first_reminder": "09:00",
        "last_reminder": "10:00",
        "closing": "11:00",
    }


async def test_schedule_day_commands_use_discord_choices() -> None:
    admin_service = MagicMock()
    schedule_service = MagicMock()
    schedule_service.add_execution_day = AsyncMock(return_value=_schedule())
    schedule_service.remove_execution_day = AsyncMock(return_value=_schedule())
    interaction = _interaction()
    group = build_config_group(admin_service, schedule_service)
    choice = app_commands.Choice(name="Domingo", value=6)

    await _agenda_command(group, "dia-adicionar").callback(interaction, choice)
    assert schedule_service.add_execution_day.await_args.kwargs["weekday"] == 6

    interaction.response.defer.reset_mock()
    await _agenda_command(group, "dia-remover").callback(interaction, choice)
    assert schedule_service.remove_execution_day.await_args.kwargs["weekday"] == 6
