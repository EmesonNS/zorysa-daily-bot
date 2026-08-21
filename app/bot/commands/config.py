"""Administrative role Slash Commands."""

from datetime import UTC, date, datetime, time

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction
from app.bot.contracts import (
    ApplicationError,
    AuditCursor,
    AuditFilters,
    AuditPage,
    AuditPresentationService,
    GuildAdminPresentationService,
    QuestionPresentationService,
    QuestionSummary,
    ReportChannelPresentationService,
    ReportChannelSummary,
    SchedulePresentationService,
    ScheduleSummary,
)
from app.domain.enums import AuditAction

_WEEKDAYS = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)
_WEEKDAY_CHOICES = [
    app_commands.Choice(name=name, value=value) for value, name in enumerate(_WEEKDAYS)
]
_AUDIT_ACTION_CHOICES = [
    app_commands.Choice(name=action.value.replace("_", " ").title(), value=action.value)
    for action in AuditAction
]


def _format_schedule(schedule: ScheduleSummary) -> str:
    status = "Ativa" if schedule.daily_enabled else "Desativada"
    days = ", ".join(_WEEKDAYS[weekday] for weekday in schedule.execution_days)
    opening, first, last, closing, reporting = schedule.formatted_times
    weekly_weekday, weekly_reporting, monthly_reporting = schedule.formatted_management_reports
    return (
        f"**Agenda automática:** {status}\n"
        f"**Timezone:** `{schedule.timezone}`\n"
        f"**Dias:** {days}\n"
        f"**Abertura:** {opening}\n"
        f"**Primeiro lembrete:** {first}\n"
        f"**Último lembrete:** {last}\n"
        f"**Fechamento:** {closing}\n"
        f"**Relatório:** {reporting}\n"
        f"Semanal: {_WEEKDAYS[weekly_weekday]} às {weekly_reporting}\n"
        f"Mensal: {monthly_reporting}"
    )


def _parse_optional_date(value: str | None, *, end_of_day: bool) -> datetime | None:
    if value is None or not value.strip():
        return None
    parsed = date.fromisoformat(value.strip())
    boundary = time.max if end_of_day else time.min
    return datetime.combine(parsed, boundary, tzinfo=UTC)


def _parse_audit_cursor(value: str | None) -> AuditCursor | None:
    if value is None or not value.strip():
        return None
    timestamp_text, event_id_text = value.strip().rsplit("|", maxsplit=1)
    timestamp = datetime.fromisoformat(timestamp_text)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    event_id = int(event_id_text)
    if event_id <= 0:
        raise ValueError("cursor inválido")
    return AuditCursor(timestamp.astimezone(UTC), event_id)


def _format_audit_page(page: AuditPage) -> str:
    if not page.events:
        return "Nenhum evento de auditoria encontrado."

    lines = []
    for event in page.events:
        occurred_at = event.occurred_at.astimezone(UTC).strftime("%d/%m/%Y %H:%M UTC")
        actor = f"<@{event.actor_user_id}>" if event.actor_user_id else "sistema"
        lines.append(
            f"`#{event.id}` • {occurred_at} • {event.action.value} • {actor} • "
            f"{event.target_type} #{event.target_id}"
        )
    if page.next_cursor is not None:
        token = f"{page.next_cursor.occurred_at.isoformat()}|{page.next_cursor.event_id}"
        lines.extend(("", f"Próximo cursor: `{token}`"))
    return "\n".join(lines)


def _format_questions(questions: tuple[QuestionSummary, ...]) -> str:
    if not questions:
        return "Nenhuma pergunta configurada."
    lines = []
    for question in questions:
        state = "Ativa" if question.active else "Inativa"
        requirement = "Obrigatória" if question.required else "Opcional"
        lines.append(
            f"{question.position}. `#{question.id}` {question.text} — {state}, {requirement}"
        )
    return "**Perguntas da daily:**\n" + "\n".join(lines)


def _format_report_channels(channels: tuple[ReportChannelSummary, ...]) -> str:
    if not channels:
        return "Nenhum canal de relatório configurado."
    lines = [
        f"• <#{channel.channel_id}> — Diário: {'sim' if channel.daily else 'não'}, "
        f"Semanal: {'sim' if channel.weekly else 'não'}, "
        f"Mensal: {'sim' if channel.monthly else 'não'}"
        for channel in channels
    ]
    return "**Canais de relatório:**\n" + "\n".join(lines)


def build_config_group(
    service: GuildAdminPresentationService,
    schedule_service: SchedulePresentationService | None = None,
    question_service: QuestionPresentationService | None = None,
    report_channel_service: ReportChannelPresentationService | None = None,
    audit_service: AuditPresentationService | None = None,
) -> app_commands.Group:
    """Build `/config admin` commands using an injected application service."""

    config = app_commands.Group(name="config", description="Configurações do Zorysa Daily Bot")
    admin = app_commands.Group(name="admin", description="Cargos administrativos")

    @admin.command(name="role-adicionar", description="Adiciona um cargo administrativo")
    @app_commands.describe(cargo="Cargo que poderá administrar o bot")
    async def add_role(interaction: discord.Interaction, cargo: discord.Role) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.add_admin_role(
                actor=actor_from_interaction(interaction),
                role_id=cargo.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"Cargo administrativo adicionado: {cargo.name}."
        )

    @admin.command(name="role-remover", description="Remove um cargo administrativo")
    @app_commands.describe(cargo="Cargo que deixará de administrar o bot")
    async def remove_role(interaction: discord.Interaction, cargo: discord.Role) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.remove_admin_role(
                actor=actor_from_interaction(interaction),
                role_id=cargo.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"Cargo administrativo removido: {cargo.name}."
        )

    @admin.command(name="roles", description="Lista os cargos com acesso administrativo")
    async def list_roles(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await service.list_admin_roles(actor=actor_from_interaction(interaction))
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return

        content = "\n".join(f"• <@&{role.role_id}>" for role in roles)
        if content:
            content = f"Cargos com acesso administrativo ao bot:\n{content}"
        await interaction.edit_original_response(
            content=content or "Nenhum cargo administrativo configurado."
        )

    config.add_command(admin)
    if schedule_service is not None:
        agenda = app_commands.Group(name="agenda", description="Agenda automática da daily")

        @agenda.command(name="visualizar", description="Mostra a agenda automática atual")
        async def view_schedule(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.get_schedule(
                    actor=actor_from_interaction(interaction)
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="horarios", description="Altera os cinco horários da agenda")
        @app_commands.rename(
            primeiro_lembrete="primeiro-lembrete",
            ultimo_lembrete="ultimo-lembrete",
        )
        @app_commands.describe(
            abertura="Horário de abertura em HH:MM",
            primeiro_lembrete="Primeiro lembrete em HH:MM",
            ultimo_lembrete="Último lembrete em HH:MM",
            fechamento="Horário de fechamento em HH:MM",
            relatorio="Horário do relatório diário em HH:MM",
        )
        async def update_times(
            interaction: discord.Interaction,
            abertura: str,
            primeiro_lembrete: str,
            ultimo_lembrete: str,
            fechamento: str,
            relatorio: str,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.update_times(
                    actor=actor_from_interaction(interaction),
                    opening=abertura,
                    first_reminder=primeiro_lembrete,
                    last_reminder=ultimo_lembrete,
                    closing=fechamento,
                    reporting=relatorio,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="timezone", description="Altera o timezone IANA da agenda")
        @app_commands.describe(valor="Timezone IANA, por exemplo America/Belem")
        async def update_timezone(interaction: discord.Interaction, valor: str) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.update_timezone(
                    actor=actor_from_interaction(interaction), timezone=valor
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="relatorios", description="Altera a agenda dos relatórios históricos")
        @app_commands.choices(dia_semanal=_WEEKDAY_CHOICES)
        @app_commands.rename(
            dia_semanal="dia-semanal",
            horario_semanal="horario-semanal",
            horario_mensal="horario-mensal",
        )
        async def update_management_report_schedule(
            interaction: discord.Interaction,
            dia_semanal: app_commands.Choice[int],
            horario_semanal: str,
            horario_mensal: str,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.update_management_reports(
                    actor=actor_from_interaction(interaction),
                    weekly_weekday=dia_semanal.value,
                    weekly_reporting=horario_semanal,
                    monthly_reporting=horario_mensal,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="dia-adicionar", description="Adiciona um dia à agenda")
        @app_commands.choices(dia=_WEEKDAY_CHOICES)
        async def add_day(interaction: discord.Interaction, dia: app_commands.Choice[int]) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.add_execution_day(
                    actor=actor_from_interaction(interaction), weekday=dia.value
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="dia-remover", description="Remove um dia da agenda")
        @app_commands.choices(dia=_WEEKDAY_CHOICES)
        async def remove_day(
            interaction: discord.Interaction, dia: app_commands.Choice[int]
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.remove_execution_day(
                    actor=actor_from_interaction(interaction), weekday=dia.value
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        config.add_command(agenda)
    if question_service is not None:
        questions = app_commands.Group(name="perguntas", description="Perguntas da daily")

        async def respond_error(interaction: discord.Interaction, error: Exception) -> None:
            await interaction.edit_original_response(content=str(error))

        @questions.command(name="listar", description="Lista as perguntas configuradas")
        async def list_questions(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await question_service.list_questions(
                    actor=actor_from_interaction(interaction)
                )
            except (ApplicationError, ValueError) as error:
                await respond_error(interaction, error)
                return
            await interaction.edit_original_response(content=_format_questions(result))

        @questions.command(name="adicionar", description="Adiciona uma pergunta ativa")
        @app_commands.describe(
            texto="Texto da nova pergunta",
            obrigatoria="Se a resposta será obrigatória",
        )
        async def add_question(
            interaction: discord.Interaction, texto: str, obrigatoria: bool
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await question_service.add_question(
                    actor=actor_from_interaction(interaction),
                    text=texto,
                    required=obrigatoria,
                )
            except (ApplicationError, ValueError) as error:
                await respond_error(interaction, error)
                return
            await interaction.edit_original_response(
                content=f"Pergunta `#{result.id}` adicionada na posição {result.position}."
            )

        @questions.command(name="editar", description="Edita uma pergunta existente")
        @app_commands.describe(
            pergunta="Pergunta que será editada",
            texto="Novo texto da pergunta",
            obrigatoria="Se a resposta será obrigatória",
        )
        async def edit_question(
            interaction: discord.Interaction,
            pergunta: int,
            texto: str,
            obrigatoria: bool,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await question_service.edit_question(
                    actor=actor_from_interaction(interaction),
                    question_id=pergunta,
                    text=texto,
                    required=obrigatoria,
                )
            except (ApplicationError, ValueError) as error:
                await respond_error(interaction, error)
                return
            await interaction.edit_original_response(content=f"Pergunta `#{result.id}` atualizada.")

        @questions.command(name="mover", description="Altera a ordem de uma pergunta")
        @app_commands.describe(
            pergunta="Pergunta que será movida",
            posicao="Nova posição da pergunta",
        )
        async def move_question(
            interaction: discord.Interaction, pergunta: int, posicao: int
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await question_service.move_question(
                    actor=actor_from_interaction(interaction),
                    question_id=pergunta,
                    position=posicao,
                )
            except (ApplicationError, ValueError) as error:
                await respond_error(interaction, error)
                return
            await interaction.edit_original_response(content=_format_questions(result))

        async def change_active(
            interaction: discord.Interaction, pergunta: int, *, active: bool
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await question_service.set_question_active(
                    actor=actor_from_interaction(interaction),
                    question_id=pergunta,
                    active=active,
                )
            except (ApplicationError, ValueError) as error:
                await respond_error(interaction, error)
                return
            state = "ativada" if result.active else "desativada"
            await interaction.edit_original_response(content=f"Pergunta `#{result.id}` {state}.")

        @questions.command(name="ativar", description="Ativa uma pergunta")
        async def activate_question(interaction: discord.Interaction, pergunta: int) -> None:
            await change_active(interaction, pergunta, active=True)

        @questions.command(name="desativar", description="Desativa uma pergunta")
        async def deactivate_question(interaction: discord.Interaction, pergunta: int) -> None:
            await change_active(interaction, pergunta, active=False)

        async def question_autocomplete(
            interaction: discord.Interaction, current: str
        ) -> list[app_commands.Choice[int]]:
            try:
                available = await question_service.list_questions(
                    actor=actor_from_interaction(interaction)
                )
            except Exception:
                return []
            query = current.casefold().strip()
            matching = (
                question
                for question in available
                if not query or query in question.text.casefold() or query in str(question.id)
            )
            return [
                app_commands.Choice(
                    name=f"#{question.id} · {question.text}"[:100],
                    value=question.id,
                )
                for question in list(matching)[:25]
            ]

        edit_question.autocomplete("pergunta")(question_autocomplete)
        move_question.autocomplete("pergunta")(question_autocomplete)
        activate_question.autocomplete("pergunta")(question_autocomplete)
        deactivate_question.autocomplete("pergunta")(question_autocomplete)
        config.add_command(questions)
    if report_channel_service is not None:
        reports = app_commands.Group(name="relatorios", description="Destinos de relatórios")

        @reports.command(name="canais", description="Lista os canais de relatório")
        async def list_report_channels(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                channels = await report_channel_service.list_channels(
                    actor=actor_from_interaction(interaction)
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_report_channels(channels))

        @reports.command(name="canal-salvar", description="Cria ou atualiza um destino")
        @app_commands.describe(
            canal="Canal que receberá relatórios",
            diario="Receber relatório diário",
            semanal="Receber relatório semanal futuro",
            mensal="Receber relatório mensal futuro",
        )
        async def save_report_channel(
            interaction: discord.Interaction,
            canal: discord.TextChannel,
            diario: bool,
            semanal: bool,
            mensal: bool,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                await report_channel_service.save_channel(
                    actor=actor_from_interaction(interaction),
                    channel_id=canal.id,
                    daily=diario,
                    weekly=semanal,
                    monthly=mensal,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(
                content=f"Canal de relatório salvo: {canal.mention}."
            )

        @reports.command(name="canal-remover", description="Remove um destino de relatório")
        async def remove_report_channel(
            interaction: discord.Interaction, canal: discord.TextChannel
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                await report_channel_service.remove_channel(
                    actor=actor_from_interaction(interaction), channel_id=canal.id
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(
                content=f"Canal de relatório removido: {canal.mention}."
            )

        config.add_command(reports)
    if audit_service is not None:
        audit = app_commands.Group(name="auditoria", description="Histórico administrativo")

        @audit.command(name="listar", description="Consulta eventos de auditoria")
        @app_commands.choices(acao=_AUDIT_ACTION_CHOICES)
        @app_commands.rename(alvo_tipo="alvo-tipo", alvo_id="alvo-id")
        @app_commands.describe(
            acao="Ação administrativa",
            ator="Usuário que executou a ação",
            alvo_tipo="Tipo do recurso afetado",
            alvo_id="ID do recurso afetado",
            inicio="Data inicial em AAAA-MM-DD",
            fim="Data final em AAAA-MM-DD",
            cursor="Cursor retornado pela página anterior",
        )
        async def list_audit_events(
            interaction: discord.Interaction,
            acao: str | None = None,
            ator: discord.Member | None = None,
            alvo_tipo: str | None = None,
            alvo_id: str | None = None,
            inicio: str | None = None,
            fim: str | None = None,
            cursor: str | None = None,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                started_at = _parse_optional_date(inicio, end_of_day=False)
                ended_at = _parse_optional_date(fim, end_of_day=True)
                if started_at is not None and ended_at is not None and started_at > ended_at:
                    raise ValueError("intervalo inválido")
                parsed_target_id = int(alvo_id) if alvo_id and alvo_id.strip() else None
                if parsed_target_id is not None and parsed_target_id <= 0:
                    raise ValueError("alvo inválido")
                filters = AuditFilters(
                    action=AuditAction(acao) if acao else None,
                    actor_user_id=ator.id if ator else None,
                    target_type=alvo_tipo.strip() if alvo_tipo and alvo_tipo.strip() else None,
                    target_id=parsed_target_id,
                    started_at=started_at,
                    ended_at=ended_at,
                )
                parsed_cursor = _parse_audit_cursor(cursor)
            except (TypeError, ValueError):
                await interaction.edit_original_response(
                    content="Informe filtros e cursor válidos para a auditoria."
                )
                return

            try:
                page = await audit_service.list_events(
                    actor=actor_from_interaction(interaction),
                    filters=filters,
                    cursor=parsed_cursor,
                    limit=10,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_audit_page(page))

        config.add_command(audit)
    return config


def register_config_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: GuildAdminPresentationService,
    schedule_service: SchedulePresentationService,
    question_service: QuestionPresentationService,
    report_channel_service: ReportChannelPresentationService,
    audit_service: AuditPresentationService | None = None,
) -> None:
    """Register the config group on a command tree."""

    tree.add_command(
        build_config_group(
            service,
            schedule_service,
            question_service,
            report_channel_service,
            audit_service,
        )
    )
