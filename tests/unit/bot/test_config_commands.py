from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.application.errors import ConflictError
from app.bot.commands.config import build_config_group
from app.bot.contracts import AdminRoleSummary, QuestionSummary, ScheduleSummary


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


def _question_command(group: app_commands.Group, name: str) -> app_commands.Command:
    questions = group.get_command("perguntas")
    assert isinstance(questions, app_commands.Group)
    command = questions.get_command(name)
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
        reporting=time(12, 10),
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
    assert "**Relatório:** 12:10" in content


async def test_update_schedule_times_passes_all_values() -> None:
    admin_service = MagicMock()
    schedule_service = MagicMock()
    schedule_service.update_times = AsyncMock(return_value=_schedule())
    interaction = _interaction()

    command = _agenda_command(build_config_group(admin_service, schedule_service), "horarios")
    await command.callback(interaction, "08:00", "09:00", "10:00", "11:00", "11:10")

    assert schedule_service.update_times.await_args.kwargs == {
        "actor": schedule_service.update_times.await_args.kwargs["actor"],
        "opening": "08:00",
        "first_reminder": "09:00",
        "last_reminder": "10:00",
        "closing": "11:00",
        "reporting": "11:10",
    }


def test_update_schedule_command_declares_report_parameter() -> None:
    command = _agenda_command(build_config_group(MagicMock(), MagicMock()), "horarios")

    assert [parameter.name for parameter in command.parameters][-1] == "relatorio"


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


def _questions() -> tuple[QuestionSummary, ...]:
    return (
        QuestionSummary(id=11, text="O que você fez?", position=1, required=True, active=True),
        QuestionSummary(id=12, text="Algum bloqueio?", position=2, required=False, active=False),
    )


def test_question_commands_are_registered() -> None:
    group = build_config_group(MagicMock(), MagicMock(), MagicMock())
    questions = group.get_command("perguntas")

    assert isinstance(questions, app_commands.Group)
    assert {command.name for command in questions.commands} == {
        "listar",
        "adicionar",
        "editar",
        "mover",
        "ativar",
        "desativar",
    }


async def test_list_questions_formats_order_state_and_requirement_ephemerally() -> None:
    service = MagicMock()
    service.list_questions = AsyncMock(return_value=_questions())
    interaction = _interaction()

    await _question_command(
        build_config_group(MagicMock(), MagicMock(), service), "listar"
    ).callback(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "1. `#11`" in content and "Ativa" in content and "Obrigatória" in content
    assert "2. `#12`" in content and "Inativa" in content and "Opcional" in content


async def test_add_and_edit_question_pass_values_to_service() -> None:
    service = MagicMock()
    service.add_question = AsyncMock(return_value=_questions()[0])
    service.edit_question = AsyncMock(return_value=_questions()[1])
    interaction = _interaction()
    group = build_config_group(MagicMock(), MagicMock(), service)

    await _question_command(group, "adicionar").callback(interaction, " Nova? ", True)
    assert service.add_question.await_args.kwargs["text"] == " Nova? "
    assert service.add_question.await_args.kwargs["required"] is True

    await _question_command(group, "editar").callback(interaction, 12, "Editada", False)
    assert service.edit_question.await_args.kwargs["question_id"] == 12
    assert service.edit_question.await_args.kwargs["required"] is False


async def test_move_activate_and_deactivate_question_pass_values() -> None:
    service = MagicMock()
    service.move_question = AsyncMock(return_value=_questions())
    service.set_question_active = AsyncMock(return_value=_questions()[0])
    interaction = _interaction()
    group = build_config_group(MagicMock(), MagicMock(), service)

    await _question_command(group, "mover").callback(interaction, 11, 2)
    assert service.move_question.await_args.kwargs["position"] == 2
    await _question_command(group, "ativar").callback(interaction, 11)
    assert service.set_question_active.await_args.kwargs["active"] is True
    await _question_command(group, "desativar").callback(interaction, 11)
    assert service.set_question_active.await_args.kwargs["active"] is False


async def test_question_id_autocomplete_filters_current_guild_and_hides_errors() -> None:
    service = MagicMock()
    service.list_questions = AsyncMock(return_value=_questions())
    interaction = _interaction()
    command = _question_command(build_config_group(MagicMock(), MagicMock(), service), "editar")
    autocomplete = command._params["pergunta"].autocomplete
    assert autocomplete is not None

    choices = await autocomplete(interaction, "bloq")
    assert [(choice.name, choice.value) for choice in choices] == [("#12 · Algum bloqueio?", 12)]
    assert service.list_questions.await_args.kwargs["actor"].guild_id == 123

    service.list_questions.side_effect = RuntimeError("internal")
    assert await autocomplete(interaction, "") == []


async def test_question_command_exposes_safe_application_error() -> None:
    service = MagicMock()
    service.add_question = AsyncMock(side_effect=ConflictError("Limite atingido."))
    interaction = _interaction()

    await _question_command(
        build_config_group(MagicMock(), MagicMock(), service), "adicionar"
    ).callback(interaction, "Pergunta", True)

    assert interaction.edit_original_response.await_args.kwargs["content"] == "Limite atingido."
