from datetime import UTC, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.application.errors import ConflictError
from app.bot.commands.config import build_config_group
from app.bot.contracts import (
    AdminRoleSummary,
    AuditCursor,
    AuditEventSummary,
    AuditPage,
    QuestionSummary,
    ReportChannelSummary,
    ScheduleSummary,
)
from app.domain.enums import AuditAction


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


def _report_command(group: app_commands.Group, name: str) -> app_commands.Command:
    reports = group.get_command("relatorios")
    assert isinstance(reports, app_commands.Group)
    command = reports.get_command(name)
    assert isinstance(command, app_commands.Command)
    return command


def _audit_command(group: app_commands.Group, name: str) -> app_commands.Command:
    audit = group.get_command("auditoria")
    assert isinstance(audit, app_commands.Group)
    command = audit.get_command(name)
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
    assert "Sexta-feira às 12:20" in content
    assert "Mensal: 12:20" in content


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


async def test_update_management_report_schedule_passes_weekday_and_times() -> None:
    schedule_service = MagicMock(update_management_reports=AsyncMock(return_value=_schedule()))
    interaction = _interaction()
    command = _agenda_command(build_config_group(MagicMock(), schedule_service), "relatorios")
    friday = app_commands.Choice(name="Sexta-feira", value=4)

    await command.callback(interaction, friday, "13:00", "14:00")

    assert schedule_service.update_management_reports.await_args.kwargs == {
        "actor": schedule_service.update_management_reports.await_args.kwargs["actor"],
        "weekly_weekday": 4,
        "weekly_reporting": "13:00",
        "monthly_reporting": "14:00",
    }


def _audit_page(*, next_cursor: bool = True) -> AuditPage:
    occurred_at = datetime(2026, 8, 21, 15, 30, tzinfo=UTC)
    return AuditPage(
        events=(
            AuditEventSummary(
                id=9,
                guild_id=123,
                actor_user_id=10,
                action=AuditAction.PROJECT_EDITED,
                target_type="project",
                target_id=77,
                details={"secret": "não exibir", "name": "interno"},
                occurred_at=occurred_at,
            ),
        ),
        next_cursor=AuditCursor(occurred_at, 9) if next_cursor else None,
    )


async def test_audit_list_parses_filters_and_paginates_ephemerally() -> None:
    audit_service = MagicMock(list_events=AsyncMock(return_value=_audit_page()))
    interaction = _interaction()
    actor = SimpleNamespace(id=20)
    group = build_config_group(MagicMock(), audit_service=audit_service)

    await _audit_command(group, "listar").callback(
        interaction,
        AuditAction.PROJECT_EDITED.value,
        actor,
        "project",
        "77",
        "2026-08-01",
        "2026-08-21",
        None,
    )

    filters = audit_service.list_events.await_args.kwargs["filters"]
    assert filters.action == AuditAction.PROJECT_EDITED
    assert filters.actor_user_id == 20
    assert filters.target_type == "project" and filters.target_id == 77
    assert filters.started_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert filters.ended_at.date().isoformat() == "2026-08-21"
    assert audit_service.list_events.await_args.kwargs["limit"] == 10
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "PROJECT_EDITED" in content and "<@10>" in content and "project #77" in content
    assert "Próximo cursor" in content and "2026-08-21T15:30:00+00:00|9" in content
    assert "secret" not in content and "interno" not in content


async def test_audit_list_accepts_cursor_and_shows_empty_state() -> None:
    audit_service = MagicMock(
        list_events=AsyncMock(return_value=AuditPage(events=(), next_cursor=None))
    )
    interaction = _interaction()
    group = build_config_group(MagicMock(), audit_service=audit_service)

    await _audit_command(group, "listar").callback(
        interaction,
        None,
        None,
        None,
        None,
        None,
        None,
        "2026-08-21T15:30:00+00:00|9",
    )

    cursor = audit_service.list_events.await_args.kwargs["cursor"]
    assert cursor == AuditCursor(datetime(2026, 8, 21, 15, 30, tzinfo=UTC), 9)
    assert interaction.edit_original_response.await_args.kwargs["content"] == (
        "Nenhum evento de auditoria encontrado."
    )


async def test_audit_list_rejects_invalid_filter_without_service_call() -> None:
    audit_service = MagicMock(list_events=AsyncMock())
    interaction = _interaction()
    group = build_config_group(MagicMock(), audit_service=audit_service)

    await _audit_command(group, "listar").callback(
        interaction, None, None, None, "inválido", None, None, None
    )

    audit_service.list_events.assert_not_awaited()
    assert "filtros" in interaction.edit_original_response.await_args.kwargs["content"]


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


def test_report_channel_commands_are_registered() -> None:
    group = build_config_group(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    reports = group.get_command("relatorios")

    assert isinstance(reports, app_commands.Group)
    assert {command.name for command in reports.commands} == {
        "canais",
        "canal-salvar",
        "canal-remover",
    }


async def test_list_report_channels_formats_mentions_and_flags_ephemerally() -> None:
    service = MagicMock()
    service.list_channels = AsyncMock(return_value=(ReportChannelSummary(100, True, False, True),))
    interaction = _interaction()

    await _report_command(
        build_config_group(MagicMock(), MagicMock(), MagicMock(), service), "canais"
    ).callback(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "<#100>" in content
    assert "Diário: sim" in content and "Semanal: não" in content and "Mensal: sim" in content


async def test_save_report_channel_passes_channel_id_and_flags() -> None:
    service = MagicMock()
    service.save_channel = AsyncMock(return_value=ReportChannelSummary(100, True, False, True))
    interaction = _interaction()
    channel = SimpleNamespace(id=100, mention="<#100>")

    await _report_command(
        build_config_group(MagicMock(), MagicMock(), MagicMock(), service), "canal-salvar"
    ).callback(interaction, channel, True, False, True)

    assert service.save_channel.await_args.kwargs["channel_id"] == 100
    assert service.save_channel.await_args.kwargs["daily"] is True
    assert service.save_channel.await_args.kwargs["weekly"] is False
    assert service.save_channel.await_args.kwargs["monthly"] is True


async def test_remove_report_channel_exposes_safe_error_ephemerally() -> None:
    service = MagicMock()
    service.remove_channel = AsyncMock(side_effect=ConflictError("Canal protegido."))
    interaction = _interaction()
    channel = SimpleNamespace(id=100, mention="<#100>")

    await _report_command(
        build_config_group(MagicMock(), MagicMock(), MagicMock(), service), "canal-remover"
    ).callback(interaction, channel)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert interaction.edit_original_response.await_args.kwargs["content"] == "Canal protegido."
