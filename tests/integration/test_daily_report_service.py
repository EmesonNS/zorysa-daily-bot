import os
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.absences import AbsenceService
from app.application.automatic_daily import AutomaticDailyService
from app.application.daily import DailyService
from app.application.daily_reports import DailyReportService
from app.application.dto import ActorContext
from app.application.guild_admin import GuildAdminService
from app.application.projects import ProjectService
from app.application.report_channels import ReportChannelService
from app.domain.enums import AssignmentStatus
from app.infrastructure.database.models import DailyAnswer, DailyAssignment, DailyQuestionSnapshot
from app.infrastructure.discord import DiscordReportGateway

TODAY = date(2026, 8, 20)


def _actor(*, roles: tuple[int, ...] = (), owner: bool = False) -> ActorContext:
    return ActorContext(9_007_000_001, "Guild Relatório", 42, roles, owner, owner)


@pytest.fixture
async def report_context():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield sessions
        finally:
            await transaction.rollback()
    await engine.dispose()


async def _seed(report_context) -> ActorContext:  # type: ignore[no-untyped-def]
    await GuildAdminService(report_context).add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    projects = ProjectService(report_context)
    for name, channel in (("Alpha", 101), ("Beta", 102)):
        await projects.create_project(actor=actor, name=name, channel_id=channel)
        await projects.add_member(
            actor=actor, project_slug=name.lower(), user_id=10, display_name="Ada"
        )
    await projects.add_member(actor=actor, project_slug="alpha", user_id=20, display_name="Linus")
    daily = DailyService(report_context, clock=lambda: datetime(2026, 8, 20, 12, tzinfo=UTC))
    alpha = await daily.open_daily(actor=actor, project_slug="alpha")
    await daily.open_daily(actor=actor, project_slug="beta")
    await AutomaticDailyService(report_context).close_guild(actor.guild_id, TODAY)
    async with report_context() as session, session.begin():
        assignment = await session.scalar(
            select(DailyAssignment).where(
                DailyAssignment.session_id == alpha.panel.session_id,
                DailyAssignment.discord_user_id == 10,
            )
        )
        question = await session.scalar(
            select(DailyQuestionSnapshot)
            .where(DailyQuestionSnapshot.session_id == alpha.panel.session_id)
            .order_by(DailyQuestionSnapshot.position)
        )
        assert assignment is not None and question is not None
        assignment.status = AssignmentStatus.ANSWERED
        assignment.answered_at = datetime.now(UTC)
        session.add(
            DailyAnswer(
                assignment_id=assignment.id,
                question_snapshot_id=question.id,
                content="Entrega completa",
            )
        )
    await AbsenceService(report_context).justify(
        actor=actor, project_slug="alpha", user_id=20, local_date=TODAY, reason="Férias"
    )
    return actor


async def test_builds_metrics_and_stable_private_details(report_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _seed(report_context)
    report = await DailyReportService(report_context).build_report(actor.guild_id, TODAY)

    assert report.metrics.project_count == 2
    assert report.metrics.unique_participants == 2
    assert report.metrics.expected_dailies == 3
    assert (report.metrics.answered, report.metrics.not_answered, report.metrics.excused) == (
        1,
        1,
        1,
    )
    assert report.metrics.response_rate == 50.0
    assert [project.name for project in report.projects] == ["Alpha", "Beta"]
    assert report.projects[0].participants[0].answers[0].content == "Entrega completa"


async def test_reserves_and_confirms_each_daily_channel_once(report_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _seed(report_context)
    channels = ReportChannelService(report_context)
    for channel_id in (500, 400):
        await channels.save_channel(
            actor=actor, channel_id=channel_id, daily=True, weekly=False, monthly=False
        )
    service = DailyReportService(report_context)

    prepared = await service.prepare_deliveries(actor.guild_id, TODAY)
    assert [item.channel_id for item in prepared] == [400, 500]
    destinations = {
        channel_id: SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=channel_id)))
        for channel_id in (400, 500)
    }
    bot = MagicMock()
    bot.get_channel.side_effect = destinations.get
    errors = await DiscordReportGateway(bot, service).publish_all(prepared)
    assert errors == ()
    assert all(destination.send.await_count >= 2 for destination in destinations.values())
    for destination in destinations.values():
        assert all(
            call.kwargs["allowed_mentions"].users is False
            for call in destination.send.await_args_list
        )
    assert await service.prepare_deliveries(actor.guild_id, TODAY) == ()


async def test_zero_sessions_and_zero_channels_are_supported(report_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _seed(report_context)
    service = DailyReportService(report_context)
    tomorrow = date(2026, 8, 21)

    report = await service.build_report(actor.guild_id, tomorrow)
    assert report.metrics.expected_dailies == 0
    assert report.projects == ()
    assert await service.prepare_deliveries(actor.guild_id, tomorrow) == ()
