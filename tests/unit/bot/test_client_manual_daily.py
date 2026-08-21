from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.client import ZorysaBot
from app.bot.views.daily import DailyResponseView


def _bot() -> ZorysaBot:
    bot = ZorysaBot(app_name="Zorysa Daily Bot")
    bot.bind_application_services(
        guild_admin_service=MagicMock(),
        schedule_service=MagicMock(),
        question_service=MagicMock(),
        report_channel_service=MagicMock(),
        audit_service=MagicMock(),
        project_service=MagicMock(),
        daily_service=MagicMock(),
        absence_service=MagicMock(),
        daily_management_service=MagicMock(),
        daily_gateway=MagicMock(),
        report_service=MagicMock(),
        report_gateway=MagicMock(),
    )
    return bot


def test_manual_daily_command_groups_are_registered_together() -> None:
    bot = _bot()

    assert bot.tree.get_command("config") is not None
    assert bot.tree.get_command("projeto") is not None
    assert bot.tree.get_command("daily") is not None
    assert bot.tree.get_command("membro") is not None
    assert bot.tree.get_command("relatorio") is not None
    assert bot.tree.get_command("health") is not None


def test_config_registers_all_management_subgroups() -> None:
    config = _bot().tree.get_command("config")
    assert isinstance(config, app_commands.Group)
    assert {command.name for command in config.commands} == {
        "admin",
        "agenda",
        "perguntas",
        "relatorios",
        "auditoria",
    }


def test_daily_registers_open_absence_status_and_close_commands() -> None:
    daily = _bot().tree.get_command("daily")
    assert isinstance(daily, app_commands.Group)
    assert {command.name for command in daily.commands} == {
        "abrir",
        "justificar",
        "status",
        "fechar",
    }


def test_application_services_cannot_be_bound_twice() -> None:
    bot = _bot()

    try:
        bot.bind_application_services(
            guild_admin_service=MagicMock(),
            schedule_service=MagicMock(),
            question_service=MagicMock(),
            report_channel_service=MagicMock(),
            audit_service=MagicMock(),
            project_service=MagicMock(),
            daily_service=MagicMock(),
            absence_service=MagicMock(),
            daily_management_service=MagicMock(),
            daily_gateway=MagicMock(),
            report_service=MagicMock(),
            report_gateway=MagicMock(),
        )
    except ValueError as error:
        assert "already" in str(error).lower()
    else:
        raise AssertionError("duplicate service composition should fail")


def test_report_group_exposes_manual_generation() -> None:
    report = _bot().tree.get_command("relatorio")
    assert isinstance(report, app_commands.Group)
    assert {command.name for command in report.commands} == {"gerar"}


def test_member_group_exposes_project_query() -> None:
    member = _bot().tree.get_command("membro")
    assert isinstance(member, app_commands.Group)
    assert {command.name for command in member.commands} == {"projetos"}


def test_audit_group_exposes_paginated_listing() -> None:
    config = _bot().tree.get_command("config")
    assert isinstance(config, app_commands.Group)
    audit = config.get_command("auditoria")
    assert isinstance(audit, app_commands.Group)
    assert {command.name for command in audit.commands} == {"listar"}


async def test_setup_registers_persistent_daily_view_before_sync() -> None:
    bot = _bot()
    bot.tree.sync = AsyncMock()
    bot.add_view = MagicMock()

    await bot.setup_hook()

    view = bot.add_view.call_args.args[0]
    assert isinstance(view, DailyResponseView)
    assert view.timeout is None
    bot.tree.sync.assert_awaited_once_with()
