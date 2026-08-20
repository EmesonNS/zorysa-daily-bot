"""Pure, paginated Discord renderer for daily reports."""

import discord

from app.application.report_dto import DailyReport
from app.domain.enums import AssignmentStatus

_DESCRIPTION_LIMIT = 4096
_DETAIL_CHUNK_LIMIT = 4000


def render_daily_report(report: DailyReport) -> tuple[discord.Embed, ...]:
    """Render a summary followed by complete detail pages within Discord limits."""

    metrics = report.metrics
    rate = f"{metrics.response_rate:.2f}".replace(".", ",")
    summary = discord.Embed(
        title=f"Relatório diário • {report.report_date.strftime('%d/%m/%Y')}",
        description=(
            f"Projetos: **{metrics.project_count}**\n"
            f"Participantes únicos: **{metrics.unique_participants}**\n"
            f"Dailies esperadas: **{metrics.expected_dailies}**\n"
            f"Respondidas: **{metrics.answered}**\n"
            f"Não respondidas: **{metrics.not_answered}**\n"
            f"Justificadas: **{metrics.excused}**\n"
            f"Taxa de resposta: **{rate}%**"
        ),
        color=discord.Color.blue(),
    )
    details = _details(report)
    if not details:
        return (summary,)
    pages = [summary]
    for index, chunk in enumerate(_chunks(details, _DETAIL_CHUNK_LIMIT), start=1):
        pages.append(
            discord.Embed(
                title=f"Detalhamento • página {index}",
                description=chunk,
                color=discord.Color.blue(),
            )
        )
    return tuple(pages)


def _details(report: DailyReport) -> str:
    blocks: list[str] = []
    labels = {
        AssignmentStatus.ANSWERED: "Respondida",
        AssignmentStatus.EXCUSED: "Justificada",
        AssignmentStatus.NOT_ANSWERED: "Não respondida",
        AssignmentStatus.PENDING: "Não respondida",
        AssignmentStatus.ABSENT: "Não respondida",
    }
    for project in report.projects:
        blocks.append(f"## Projeto: {_safe(project.name)}\n")
        for participant in project.participants:
            blocks.append(f"### {_safe(participant.display_name)} — {labels[participant.status]}\n")
            for answer in participant.answers:
                blocks.append(f"**{_safe(answer.question)}**\n{_safe(answer.content)}\n")
            blocks.append("\n")
    return "".join(blocks)


def _safe(value: str) -> str:
    return value.replace("<@", "<＠")


def _chunks(value: str, limit: int) -> tuple[str, ...]:
    if limit > _DESCRIPTION_LIMIT:
        raise ValueError("O limite de paginação excede o limite do Discord.")
    return tuple(value[index : index + limit] for index in range(0, len(value), limit))
