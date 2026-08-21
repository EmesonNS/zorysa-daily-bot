import os
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.errors import NotFoundError, ValidationError
from app.application.historical_reports import HistoricalReportService
from app.application.report_dto import ReportPeriod
from app.domain.enums import AssignmentStatus, ProjectStatus, ReportKind, SessionStatus
from app.infrastructure.database.models import (
    DailyAnswer,
    DailyAssignment,
    DailyQuestionSnapshot,
    DailySession,
    Guild,
    GuildSettings,
    Project,
    ReportChannel,
)

GUILD_ID = 9_007_000_101
WEEK = ReportPeriod(
    ReportKind.WEEKLY,
    date(2026, 8, 17),
    date(2026, 8, 23),
    "17/08/2026 a 23/08/2026",
)
MONTH = ReportPeriod(
    ReportKind.MONTHLY,
    date(2026, 8, 1),
    date(2026, 8, 31),
    "08/2026",
)


@pytest.fixture
async def historical_context():  # type: ignore[no-untyped-def]
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


async def _add_session(
    session,  # type: ignore[no-untyped-def]
    *,
    project_id: int,
    local_date: date,
    user_id: int,
    display_name: str,
    status: AssignmentStatus,
    answer: str | None = None,
) -> None:
    daily = DailySession(
        project_id=project_id,
        session_date=local_date,
        status=SessionStatus.CLOSED,
        closed_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    session.add(daily)
    await session.flush()
    question = DailyQuestionSnapshot(
        session_id=daily.id,
        text="O que foi concluído?",
        position=1,
        required=True,
    )
    assignment = DailyAssignment(
        session_id=daily.id,
        discord_user_id=user_id,
        display_name=display_name,
        status=status,
        answered_at=(datetime(2026, 8, 17, 10, tzinfo=UTC) if answer else None),
        excused_at=(
            datetime(2026, 8, 17, 9, tzinfo=UTC) if status == AssignmentStatus.EXCUSED else None
        ),
        excused_by_user_id=(42 if status == AssignmentStatus.EXCUSED else None),
        excuse_reason=("conteúdo privado" if status == AssignmentStatus.EXCUSED else None),
    )
    session.add_all((question, assignment))
    await session.flush()
    if answer is not None:
        session.add(
            DailyAnswer(
                assignment_id=assignment.id,
                question_snapshot_id=question.id,
                content=answer,
            )
        )


async def _seed(historical_context) -> None:  # type: ignore[no-untyped-def]
    async with historical_context() as session, session.begin():
        guild = Guild(discord_guild_id=GUILD_ID, name="Guild Histórica")
        session.add(guild)
        await session.flush()
        session.add(GuildSettings(guild_id=guild.id))
        alpha = Project(
            guild_id=guild.id,
            name="Alpha",
            slug="alpha",
            discord_channel_id=101,
        )
        beta = Project(
            guild_id=guild.id,
            name="Beta Antigo",
            slug="beta",
            discord_channel_id=102,
            status=ProjectStatus.ARCHIVED,
            daily_enabled=False,
        )
        gamma = Project(
            guild_id=guild.id,
            name="Gamma Vazio",
            slug="gamma",
            discord_channel_id=103,
        )
        session.add_all((alpha, beta, gamma))
        await session.flush()
        await _add_session(
            session,
            project_id=alpha.id,
            local_date=date(2026, 8, 17),
            user_id=10,
            display_name="Ada",
            status=AssignmentStatus.ANSWERED,
            answer="Entrega histórica",
        )
        await _add_session(
            session,
            project_id=alpha.id,
            local_date=date(2026, 8, 18),
            user_id=10,
            display_name="Ada",
            status=AssignmentStatus.NOT_ANSWERED,
        )
        await _add_session(
            session,
            project_id=beta.id,
            local_date=date(2026, 8, 19),
            user_id=20,
            display_name="Linus",
            status=AssignmentStatus.EXCUSED,
        )
        await _add_session(
            session,
            project_id=alpha.id,
            local_date=date(2026, 7, 31),
            user_id=30,
            display_name="Grace",
            status=AssignmentStatus.ANSWERED,
            answer="Fora do período",
        )


async def test_weekly_report_aggregates_snapshots_and_distinct_projects(
    historical_context,
) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)

    report = await HistoricalReportService(historical_context).build_report(
        GUILD_ID, ReportKind.WEEKLY, WEEK
    )

    assert report.metrics.project_count == 2
    assert report.metrics.unique_participants == 2
    assert report.metrics.expected_dailies == 3
    assert (report.metrics.answered, report.metrics.not_answered, report.metrics.excused) == (
        1,
        1,
        1,
    )
    assert report.metrics.response_rate == 50.0
    assert [project.name for project in report.projects] == ["Alpha", "Beta Antigo"]
    assert report.projects[0].entries[0].answers[0].content == "Entrega histórica"


async def test_monthly_report_excludes_sessions_outside_month(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)

    report = await HistoricalReportService(historical_context).build_report(
        GUILD_ID, ReportKind.MONTHLY, MONTH
    )

    assert report.metrics.expected_dailies == 3
    assert all(
        entry.local_date.month == 8 for project in report.projects for entry in project.entries
    )


async def test_archived_project_can_be_filtered_by_slug(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)

    report = await HistoricalReportService(historical_context).build_report(
        GUILD_ID, ReportKind.WEEKLY, WEEK, project_slug="beta"
    )

    assert [project.slug for project in report.projects] == ["beta"]
    assert report.metrics.expected_dailies == 1


async def test_valid_project_without_sessions_returns_empty_report(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)

    report = await HistoricalReportService(historical_context).build_report(
        GUILD_ID, ReportKind.WEEKLY, WEEK, project_slug="gamma"
    )

    assert report.projects == ()
    assert report.metrics.expected_dailies == 0


async def test_unknown_project_slug_is_rejected(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)

    with pytest.raises(NotFoundError, match="Projeto não encontrado"):
        await HistoricalReportService(historical_context).build_report(
            GUILD_ID, ReportKind.WEEKLY, WEEK, project_slug="inexistente"
        )


@pytest.mark.parametrize("kind", tuple(ReportKind))
async def test_unknown_guild_returns_valid_empty_report(
    historical_context, kind: ReportKind
) -> None:  # type: ignore[no-untyped-def]
    period = ReportPeriod(kind, date(2026, 8, 21), date(2026, 8, 21), "vazio")

    report = await HistoricalReportService(historical_context).build_report(
        999_999_999, kind, period
    )

    assert report.projects == ()
    assert report.metrics.expected_dailies == 0


@pytest.mark.parametrize(
    ("kind", "expected_channel"),
    [
        (ReportKind.DAILY, 401),
        (ReportKind.WEEKLY, 402),
        (ReportKind.MONTHLY, 403),
    ],
)
async def test_delivery_reservations_isolate_channel_flags(
    historical_context, kind: ReportKind, expected_channel: int
) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)
    async with historical_context() as session, session.begin():
        guild = await session.scalar(select(Guild).where(Guild.discord_guild_id == GUILD_ID))
        assert guild is not None
        session.add_all(
            (
                ReportChannel(
                    guild_id=guild.id,
                    discord_channel_id=401,
                    daily_enabled=True,
                    weekly_enabled=False,
                    monthly_enabled=False,
                ),
                ReportChannel(
                    guild_id=guild.id,
                    discord_channel_id=402,
                    daily_enabled=False,
                    weekly_enabled=True,
                    monthly_enabled=False,
                ),
                ReportChannel(
                    guild_id=guild.id,
                    discord_channel_id=403,
                    daily_enabled=False,
                    weekly_enabled=False,
                    monthly_enabled=True,
                ),
            )
        )

    prepared = await HistoricalReportService(historical_context).prepare_deliveries(
        GUILD_ID, kind, date(2026, 8, 21)
    )

    assert [item.channel_id for item in prepared] == [expected_channel]
    assert all(item.report.kind == kind for item in prepared)


async def test_pending_delivery_is_reused_without_duplicate(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)
    async with historical_context() as session, session.begin():
        guild = await session.scalar(select(Guild).where(Guild.discord_guild_id == GUILD_ID))
        assert guild is not None
        session.add(ReportChannel(guild_id=guild.id, discord_channel_id=402))
        await session.flush()
        channel = await session.scalar(
            select(ReportChannel).where(ReportChannel.discord_channel_id == 402)
        )
        assert channel is not None
        channel.daily_enabled = False
        channel.weekly_enabled = True

    service = HistoricalReportService(historical_context)
    first = await service.prepare_deliveries(GUILD_ID, ReportKind.WEEKLY, date(2026, 8, 21))
    second = await service.prepare_deliveries(GUILD_ID, ReportKind.WEEKLY, date(2026, 8, 21))

    assert first[0].delivery_id == second[0].delivery_id


async def test_confirmed_delivery_is_not_prepared_again(historical_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(historical_context)
    async with historical_context() as session, session.begin():
        guild = await session.scalar(select(Guild).where(Guild.discord_guild_id == GUILD_ID))
        assert guild is not None
        session.add(
            ReportChannel(
                guild_id=guild.id,
                discord_channel_id=402,
                daily_enabled=False,
                weekly_enabled=True,
            )
        )
    service = HistoricalReportService(historical_context)
    prepared = await service.prepare_deliveries(GUILD_ID, ReportKind.WEEKLY, date(2026, 8, 21))

    await service.attach_delivery(prepared[0].delivery_id, page_count=3)

    assert await service.prepare_deliveries(GUILD_ID, ReportKind.WEEKLY, date(2026, 8, 21)) == ()


@pytest.mark.parametrize("page_count", [0, -1])
async def test_attach_delivery_rejects_invalid_page_count(
    historical_context, page_count: int
) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError, match="páginas"):
        await HistoricalReportService(historical_context).attach_delivery(1, page_count=page_count)


async def test_attach_delivery_rejects_unknown_reservation(historical_context) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(NotFoundError, match="Reserva"):
        await HistoricalReportService(historical_context).attach_delivery(999_999, page_count=1)
