from datetime import date

import discord

from app.application.report_dto import (
    DailyReport,
    DailyReportAnswer,
    DailyReportMetrics,
    DailyReportParticipant,
    DailyReportProject,
)
from app.bot.embeds.report import render_daily_report
from app.domain.enums import AssignmentStatus


def _report(*, content: str = "Entrega completa") -> DailyReport:
    return DailyReport(
        report_date=date(2026, 8, 20),
        metrics=DailyReportMetrics(1, 3, 3, 1, 1, 1, 50.0),
        projects=(
            DailyReportProject(
                "Alpha",
                (
                    DailyReportParticipant(
                        10,
                        "Ada",
                        AssignmentStatus.ANSWERED,
                        (DailyReportAnswer("O que fez?", content),),
                    ),
                    DailyReportParticipant(20, "Linus", AssignmentStatus.NOT_ANSWERED, ()),
                    DailyReportParticipant(30, "Grace", AssignmentStatus.EXCUSED, ()),
                ),
            ),
        ),
    )


def test_first_page_contains_complete_summary() -> None:
    pages = render_daily_report(_report())
    assert isinstance(pages[0], discord.Embed)
    assert pages[0].title == "Relatório diário • 20/08/2026"
    summary = pages[0].description or ""
    assert "Projetos: **1**" in summary
    assert "Participantes únicos: **3**" in summary
    assert "Taxa de resposta: **50,00%**" in summary


def test_details_group_project_and_states_without_mentions_or_excuse_reason() -> None:
    pages = render_daily_report(_report(content="Revisão com <@123>"))
    details = "".join(page.description or "" for page in pages[1:])
    assert "Alpha" in details and "Ada" in details
    assert "Respondida" in details and "Não respondida" in details and "Justificada" in details
    assert "<@" not in details
    assert "motivo" not in details.casefold()


def test_long_answers_are_paginated_without_truncation() -> None:
    content = "abcde " * 2500
    pages = render_daily_report(_report(content=content))
    details = "".join(page.description or "" for page in pages[1:])
    assert content in details
    assert len(pages) > 2
    assert all(len(page.description or "") <= 4096 for page in pages)
    assert all(len(page) <= 6000 for page in pages)


def test_empty_report_still_has_one_summary_page() -> None:
    report = DailyReport(date(2026, 8, 20), DailyReportMetrics(0, 0, 0, 0, 0, 0, 0.0), ())
    pages = render_daily_report(report)
    assert len(pages) == 1
    assert "Projetos: **0**" in (pages[0].description or "")


def test_renderer_is_deterministic() -> None:
    assert [page.to_dict() for page in render_daily_report(_report())] == [
        page.to_dict() for page in render_daily_report(_report())
    ]
