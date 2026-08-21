"""Historical report aggregation and idempotent delivery reservations."""

from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.dto import ActorContext
from app.application.errors import NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.application.report_dto import (
    DailyReport,
    DailyReportAnswer,
    DailyReportMetrics,
    DailyReportParticipant,
    DailyReportProject,
    HistoricalReport,
    HistoricalReportEntry,
    HistoricalReportProject,
    ManualReport,
    PreparedReport,
    ReportPeriod,
)
from app.application.report_periods import resolve_period
from app.domain.enums import AssignmentStatus, AuditAction, ReportKind
from app.infrastructure.database.models import (
    DailyAnswer,
    DailyAssignment,
    DailyQuestionSnapshot,
    DailySession,
    Guild,
    GuildSettings,
    Project,
    ReportChannel,
    ReportDelivery,
)


class _ReportChannelFlags(Protocol):
    daily_enabled: bool
    weekly_enabled: bool
    monthly_enabled: bool


def calculate_metrics(
    *, project_count: int, assignments: Iterable[tuple[int, AssignmentStatus]]
) -> DailyReportMetrics:
    """Calculate stable metrics shared by every report period."""

    values = tuple(assignments)
    answered = sum(status == AssignmentStatus.ANSWERED for _, status in values)
    excused = sum(status == AssignmentStatus.EXCUSED for _, status in values)
    not_answered = len(values) - answered - excused
    denominator = answered + not_answered
    rate = round(answered * 100 / denominator, 2) if denominator else 0.0
    return DailyReportMetrics(
        project_count=project_count,
        unique_participants=len({user_id for user_id, _ in values}),
        expected_dailies=len(values),
        answered=answered,
        not_answered=not_answered,
        excused=excused,
        response_rate=rate,
    )


def report_kind_enabled(kind: ReportKind, channel: _ReportChannelFlags) -> bool:
    """Return only the destination flag corresponding to a report kind."""

    return {
        ReportKind.DAILY: channel.daily_enabled,
        ReportKind.WEEKLY: channel.weekly_enabled,
        ReportKind.MONTHLY: channel.monthly_enabled,
    }[kind]


def as_daily_report(report: HistoricalReport) -> DailyReport:
    """Convert a one-day historical report to the legacy public contract."""

    if report.kind != ReportKind.DAILY:
        raise ValueError("Only a daily historical report can use the legacy daily contract.")
    projects = tuple(
        DailyReportProject(
            project.name,
            tuple(
                DailyReportParticipant(
                    entry.user_id,
                    entry.display_name,
                    entry.status,
                    entry.answers,
                )
                for entry in project.entries
            ),
        )
        for project in report.projects
    )
    return DailyReport(report.period.start, report.metrics, projects)


class HistoricalReportService:
    """Build snapshot-only reports and reserve their automatic publications."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone
        self._clock = clock or (lambda: datetime.now(UTC))

    async def build_manual(
        self,
        *,
        actor: ActorContext,
        kind: ReportKind,
        period_text: str | None,
        project_slug: str | None,
        channel_id: int,
    ) -> ManualReport:
        """Authorize, build, and audit a repeatable manual report request."""

        if channel_id <= 0:
            raise ValidationError("O canal atual não permite publicar relatórios.")
        selected_slug = project_slug.strip().lower() if project_slug else None
        async with self._sessions() as session, session.begin():
            guild = await ensure_guild_record(
                session,
                discord_guild_id=actor.guild_id,
                guild_name=actor.guild_name,
                timezone=self._timezone,
            )
            await authorize_admin(session, guild=guild, actor=actor)
            timezone = await session.scalar(
                select(GuildSettings.timezone).where(GuildSettings.guild_id == guild.id)
            )
            local_today = self._now().astimezone(ZoneInfo(timezone or self._timezone)).date()
            period = resolve_period(kind, period_text, local_today)

        report = await self.build_report(
            actor.guild_id,
            kind,
            period,
            project_slug=selected_slug,
        )
        async with self._sessions() as session, session.begin():
            guild = await ensure_guild_record(
                session,
                discord_guild_id=actor.guild_id,
                guild_name=actor.guild_name,
                timezone=self._timezone,
            )
            await authorize_admin(session, guild=guild, actor=actor)
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.MANUAL_REPORT_REQUESTED,
                target_type="report_channel",
                target_id=channel_id,
                details={
                    "kind": kind.value,
                    "period_start": period.start.isoformat(),
                    "period_end": period.end.isoformat(),
                    "project_slug": selected_slug,
                },
            )
        return ManualReport(channel_id=channel_id, report=report)

    async def build_report(
        self,
        discord_guild_id: int,
        kind: ReportKind,
        period: ReportPeriod,
        *,
        project_slug: str | None = None,
    ) -> HistoricalReport:
        """Aggregate only persisted session snapshots inside one guild and period."""

        async with self._sessions() as session:
            guild_id = await session.scalar(
                select(Guild.id).where(Guild.discord_guild_id == discord_guild_id)
            )
            if guild_id is None:
                return self._empty(kind, period)
            project_id: int | None = None
            if project_slug is not None:
                project_id = await session.scalar(
                    select(Project.id).where(
                        Project.guild_id == guild_id,
                        Project.slug == project_slug,
                    )
                )
                if project_id is None:
                    raise NotFoundError("Projeto não encontrado nesta guild.")
            sessions_query = (
                select(DailySession, Project)
                .join(Project, Project.id == DailySession.project_id)
                .where(
                    Project.guild_id == guild_id,
                    DailySession.session_date >= period.start,
                    DailySession.session_date <= period.end,
                )
                .order_by(Project.name, Project.id, DailySession.session_date, DailySession.id)
            )
            if project_id is not None:
                sessions_query = sessions_query.where(Project.id == project_id)
            session_rows = (await session.execute(sessions_query)).all()
            session_ids = [daily.id for daily, _ in session_rows]
            assignments = (
                (
                    await session.scalars(
                        select(DailyAssignment)
                        .where(DailyAssignment.session_id.in_(session_ids))
                        .order_by(
                            DailyAssignment.session_id,
                            DailyAssignment.display_name,
                            DailyAssignment.id,
                        )
                    )
                ).all()
                if session_ids
                else []
            )
            answers_by_assignment = await self._load_answers(session, assignments)
            assignments_by_session: dict[int, list[DailyAssignment]] = {}
            for assignment in assignments:
                assignments_by_session.setdefault(assignment.session_id, []).append(assignment)
            grouped: dict[int, tuple[Project, list[HistoricalReportEntry]]] = {}
            for daily, project in session_rows:
                stored = grouped.setdefault(project.id, (project, []))
                stored[1].extend(
                    HistoricalReportEntry(
                        local_date=daily.session_date,
                        user_id=assignment.discord_user_id,
                        display_name=assignment.display_name,
                        status=assignment.status,
                        answers=tuple(answers_by_assignment.get(assignment.id, ())),
                    )
                    for assignment in assignments_by_session.get(daily.id, ())
                )
            projects = tuple(
                HistoricalReportProject(project.name, project.slug, tuple(entries))
                for project, entries in grouped.values()
            )
            metrics = calculate_metrics(
                project_count=len(grouped),
                assignments=(
                    (assignment.discord_user_id, assignment.status) for assignment in assignments
                ),
            )
            return HistoricalReport(kind, period, metrics, projects)

    async def prepare_deliveries(
        self, discord_guild_id: int, kind: ReportKind, reference_date: date
    ) -> tuple[PreparedReport, ...]:
        """Reserve each enabled destination once for the resolved report period."""

        period = resolve_period(kind, None, reference_date)
        report = await self.build_report(discord_guild_id, kind, period)
        async with self._sessions() as session, session.begin():
            guild_id = await session.scalar(
                select(Guild.id).where(Guild.discord_guild_id == discord_guild_id)
            )
            if guild_id is None:
                return ()
            channels = (
                await session.scalars(
                    select(ReportChannel)
                    .where(ReportChannel.guild_id == guild_id)
                    .order_by(ReportChannel.discord_channel_id, ReportChannel.id)
                )
            ).all()
            prepared: list[PreparedReport] = []
            for channel in channels:
                if not report_kind_enabled(kind, channel):
                    continue
                delivery_id = await session.scalar(
                    insert(ReportDelivery)
                    .values(
                        guild_id=guild_id,
                        kind=kind,
                        period_start=period.start,
                        period_end=period.end,
                        discord_channel_id=channel.discord_channel_id,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_report_deliveries_guild_kind_period_channel"
                    )
                    .returning(ReportDelivery.id)
                )
                delivery = (
                    await session.get(ReportDelivery, delivery_id)
                    if delivery_id is not None
                    else await session.scalar(
                        select(ReportDelivery).where(
                            ReportDelivery.guild_id == guild_id,
                            ReportDelivery.kind == kind,
                            ReportDelivery.period_start == period.start,
                            ReportDelivery.period_end == period.end,
                            ReportDelivery.discord_channel_id == channel.discord_channel_id,
                        )
                    )
                )
                if delivery is not None and delivery.sent_at is None:
                    prepared.append(PreparedReport(delivery.id, channel.discord_channel_id, report))
            return tuple(prepared)

    async def attach_delivery(self, delivery_id: int, *, page_count: int) -> None:
        """Confirm a fully published delivery."""

        if page_count <= 0:
            raise ValidationError("A quantidade de páginas do relatório é inválida.")
        async with self._sessions() as session, session.begin():
            delivery = await session.get(ReportDelivery, delivery_id)
            if delivery is None:
                raise NotFoundError("Reserva de relatório não encontrada.")
            delivery.page_count = page_count
            if delivery.sent_at is None:
                delivery.sent_at = self._now()

    async def _load_answers(
        self, session: AsyncSession, assignments: Sequence[DailyAssignment]
    ) -> dict[int, list[DailyReportAnswer]]:
        answers_by_assignment: dict[int, list[DailyReportAnswer]] = {}
        if not assignments:
            return answers_by_assignment
        rows = (
            await session.execute(
                select(DailyAnswer, DailyQuestionSnapshot)
                .join(
                    DailyQuestionSnapshot,
                    DailyQuestionSnapshot.id == DailyAnswer.question_snapshot_id,
                )
                .where(DailyAnswer.assignment_id.in_([item.id for item in assignments]))
                .order_by(DailyAnswer.assignment_id, DailyQuestionSnapshot.position)
            )
        ).all()
        for answer, question in rows:
            answers_by_assignment.setdefault(answer.assignment_id, []).append(
                DailyReportAnswer(question.text, answer.content)
            )
        return answers_by_assignment

    @staticmethod
    def _empty(kind: ReportKind, period: ReportPeriod) -> HistoricalReport:
        return HistoricalReport(
            kind,
            period,
            calculate_metrics(project_count=0, assignments=()),
            (),
        )

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
