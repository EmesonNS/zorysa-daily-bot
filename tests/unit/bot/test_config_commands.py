from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.commands.config import build_config_group
from app.bot.contracts import AdminRoleSummary


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
