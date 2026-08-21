from datetime import date

import discord
import pytest

from app.application.report_dto import (
    DailyReportAnswer,
    DailyReportMetrics,
    HistoricalReport,
    HistoricalReportEntry,
    HistoricalReportProject,
    ReportPeriod,
)
from app.bot.embeds.report import render_report
from app.domain.enums import AssignmentStatus, ReportKind


def _report(
    *, kind: ReportKind = ReportKind.WEEKLY, content: str = "Entrega completa"
) -> HistoricalReport:
    labels = {
        ReportKind.DAILY: "20/08/2026",
        ReportKind.WEEKLY: "17/08/2026 a 23/08/2026",
        ReportKind.MONTHLY: "08/2026",
    }
    period = ReportPeriod(kind, date(2026, 8, 17), date(2026, 8, 23), labels[kind])
    return HistoricalReport(
        kind=kind,
        period=period,
        metrics=DailyReportMetrics(1, 3, 3, 1, 1, 1, 50.0),
        projects=(
            HistoricalReportProject(
                "Alpha",
                "alpha",
                (
                    HistoricalReportEntry(
                        date(2026, 8, 17),
                        10,
                        "Ada",
                        AssignmentStatus.ANSWERED,
                        (DailyReportAnswer("O que fez?", content),),
                    ),
                    HistoricalReportEntry(
                        date(2026, 8, 18),
                        20,
                        "Linus",
                        AssignmentStatus.NOT_ANSWERED,
                        (),
                    ),
                    HistoricalReportEntry(
                        date(2026, 8, 19),
                        30,
                        "Grace",
                        AssignmentStatus.EXCUSED,
                        (),
                    ),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("kind", "expected_title"),
    [
        (ReportKind.DAILY, "Relatório diário • 20/08/2026"),
        (ReportKind.WEEKLY, "Relatório semanal • 17/08/2026 a 23/08/2026"),
        (ReportKind.MONTHLY, "Relatório mensal • 08/2026"),
    ],
)
def test_summary_title_distinguishes_report_kind(kind: ReportKind, expected_title: str) -> None:
    pages = render_report(_report(kind=kind))

    assert isinstance(pages[0], discord.Embed)
    assert pages[0].title == expected_title


def test_summary_contains_complete_historical_metrics() -> None:
    summary = render_report(_report())[0].description or ""

    assert "Projetos: **1**" in summary
    assert "Participantes únicos: **3**" in summary
    assert "Dailies esperadas: **3**" in summary
    assert "Taxa de resposta: **50,00%**" in summary


def test_details_include_date_project_person_state_and_complete_answer() -> None:
    details = "".join(page.description or "" for page in render_report(_report())[1:])

    assert "Projeto: Alpha" in details
    assert "17/08/2026 • Ada — Respondida" in details
    assert "18/08/2026 • Linus — Não respondida" in details
    assert "19/08/2026 • Grace — Justificada" in details
    assert "O que fez?" in details
    assert "Entrega completa" in details


def test_historical_details_never_create_mentions_or_show_excuse_reason() -> None:
    details = "".join(
        page.description or "" for page in render_report(_report(content="Revisão <@123>"))[1:]
    )

    assert "<@" not in details
    assert "motivo" not in details.casefold()


def test_long_historical_answers_are_paginated_without_truncation() -> None:
    content = "abcde " * 2500
    pages = render_report(_report(content=content))
    details = "".join(page.description or "" for page in pages[1:])

    assert content in details
    assert len(pages) > 2
    assert all(len(page.description or "") <= 4096 for page in pages)
    assert all(len(page) <= 6000 for page in pages)


def test_empty_historical_report_has_only_summary() -> None:
    period = ReportPeriod(
        ReportKind.MONTHLY,
        date(2026, 8, 1),
        date(2026, 8, 31),
        "08/2026",
    )
    report = HistoricalReport(
        ReportKind.MONTHLY,
        period,
        DailyReportMetrics(0, 0, 0, 0, 0, 0, 0.0),
        (),
    )

    pages = render_report(report)

    assert len(pages) == 1
    assert "Projetos: **0**" in (pages[0].description or "")
