"""Daily report consolidation and idempotent delivery reservations."""

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.errors import NotFoundError, ValidationError
from app.application.report_dto import (
    DailyReport,
    DailyReportAnswer,
    DailyReportMetrics,
    DailyReportParticipant,
    DailyReportProject,
    PreparedDailyReport,
)
from app.domain.enums import AssignmentStatus
from app.infrastructure.database.models import (
    DailyAnswer,
    DailyAssignment,
    DailyQuestionSnapshot,
    DailyReportDelivery,
    DailySession,
    Guild,
    Project,
    ReportChannel,
)


def calculate_metrics(
    *, project_count: int, assignments: Iterable[tuple[int, AssignmentStatus]]
) -> DailyReportMetrics:
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


class DailyReportService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._clock = clock or (lambda: datetime.now(UTC))

    async def build_report(self, discord_guild_id: int, report_date: date) -> DailyReport:
        async with self._sessions() as session:
            guild_id = await session.scalar(
                select(Guild.id).where(Guild.discord_guild_id == discord_guild_id)
            )
            if guild_id is None:
                return DailyReport(
                    report_date, calculate_metrics(project_count=0, assignments=()), ()
                )
            session_rows = (
                await session.execute(
                    select(DailySession, Project)
                    .join(Project, Project.id == DailySession.project_id)
                    .where(Project.guild_id == guild_id, DailySession.session_date == report_date)
                    .order_by(Project.name, DailySession.id)
                )
            ).all()
            session_ids = [daily_session.id for daily_session, _ in session_rows]
            assignments = (
                (
                    await session.scalars(
                        select(DailyAssignment)
                        .where(DailyAssignment.session_id.in_(session_ids))
                        .order_by(DailyAssignment.display_name, DailyAssignment.id)
                    )
                ).all()
                if session_ids
                else []
            )
            answers_by_assignment: dict[int, list[DailyReportAnswer]] = {}
            if assignments:
                answer_rows = (
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
                for answer, question in answer_rows:
                    answers_by_assignment.setdefault(answer.assignment_id, []).append(
                        DailyReportAnswer(question.text, answer.content)
                    )
            by_session: dict[int, list[DailyAssignment]] = {}
            for assignment in assignments:
                by_session.setdefault(assignment.session_id, []).append(assignment)
            projects = tuple(
                DailyReportProject(
                    name=project.name,
                    participants=tuple(
                        DailyReportParticipant(
                            user_id=assignment.discord_user_id,
                            display_name=assignment.display_name,
                            status=assignment.status,
                            answers=tuple(answers_by_assignment.get(assignment.id, ())),
                        )
                        for assignment in by_session.get(daily_session.id, ())
                    ),
                )
                for daily_session, project in session_rows
            )
            metrics = calculate_metrics(
                project_count=len(session_rows),
                assignments=(
                    (assignment.discord_user_id, assignment.status) for assignment in assignments
                ),
            )
            return DailyReport(report_date, metrics, projects)

    async def prepare_deliveries(
        self, discord_guild_id: int, report_date: date
    ) -> tuple[PreparedDailyReport, ...]:
        report = await self.build_report(discord_guild_id, report_date)
        async with self._sessions() as session, session.begin():
            guild_id = await session.scalar(
                select(Guild.id).where(Guild.discord_guild_id == discord_guild_id)
            )
            if guild_id is None:
                return ()
            channels = (
                await session.scalars(
                    select(ReportChannel)
                    .where(
                        ReportChannel.guild_id == guild_id,
                        ReportChannel.daily_enabled.is_(True),
                    )
                    .order_by(ReportChannel.discord_channel_id)
                )
            ).all()
            prepared: list[PreparedDailyReport] = []
            for channel in channels:
                delivery = await session.scalar(
                    select(DailyReportDelivery).where(
                        DailyReportDelivery.guild_id == guild_id,
                        DailyReportDelivery.report_date == report_date,
                        DailyReportDelivery.discord_channel_id == channel.discord_channel_id,
                    )
                )
                if delivery is not None and delivery.sent_at is not None:
                    continue
                if delivery is None:
                    delivery = DailyReportDelivery(
                        guild_id=guild_id,
                        report_date=report_date,
                        discord_channel_id=channel.discord_channel_id,
                    )
                    session.add(delivery)
                    await session.flush()
                prepared.append(
                    PreparedDailyReport(delivery.id, channel.discord_channel_id, report)
                )
            return tuple(prepared)

    async def attach_delivery(self, delivery_id: int, *, page_count: int) -> None:
        if page_count <= 0:
            raise ValidationError("A quantidade de páginas do relatório é inválida.")
        async with self._sessions() as session, session.begin():
            delivery = await session.get(DailyReportDelivery, delivery_id)
            if delivery is None:
                raise NotFoundError("Reserva de relatório não encontrada.")
            delivery.page_count = page_count
            if delivery.sent_at is None:
                delivery.sent_at = self._now()

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
