"""Manual daily session application service."""

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.daily_dto import (
    DailyPanel,
    DailyParticipant,
    DailyResponseForm,
    OpenedDaily,
    QuestionPrompt,
)
from app.application.dto import ActorContext
from app.application.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AssignmentStatus, ProjectStatus, SessionStatus
from app.infrastructure.database.models import (
    DailyAnswer,
    DailyAssignment,
    DailyQuestion,
    DailyQuestionSnapshot,
    DailySession,
    Guild,
    GuildSettings,
    Project,
    ProjectMembership,
)


class DailyService:
    """Open daily sessions and persist private member responses."""

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

    async def open_daily(self, *, actor: ActorContext, project_slug: str) -> OpenedDaily:
        """Open or reuse today's session and snapshot members and questions."""

        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                project = await self._project(session, guild, project_slug)
                if project.status != ProjectStatus.ACTIVE or not project.daily_enabled:
                    raise ConflictError("A daily deste projeto não está habilitada.")

                timezone = await session.scalar(
                    select(GuildSettings.timezone).where(GuildSettings.guild_id == guild.id)
                )
                local_date = self._now().astimezone(ZoneInfo(timezone or self._timezone)).date()
                return await _open_project_session(
                    session,
                    guild=guild,
                    project=project,
                    local_date=local_date,
                    opened_at=self._now(),
                )
        except IntegrityError as error:
            raise ConflictError(
                "A daily está sendo aberta por outra interação; tente novamente."
            ) from error

    async def attach_message(self, *, session_id: int, message_id: int) -> None:
        """Attach the single Discord message published for a session."""

        if message_id <= 0:
            raise ValidationError("A mensagem publicada é inválida.")
        try:
            async with self._sessions() as session, session.begin():
                daily_session = await session.get(DailySession, session_id)
                if daily_session is None:
                    raise NotFoundError("Sessão de daily não encontrada.")
                if daily_session.message_id not in (None, message_id):
                    raise ConflictError("Esta daily já possui uma mensagem publicada.")
                daily_session.message_id = message_id
        except IntegrityError as error:
            raise ConflictError("Esta mensagem já pertence a outra daily.") from error

    async def prepare_response(self, *, message_id: int, user_id: int) -> DailyResponseForm:
        """Authorize a snapshotted participant and return their modal prompts."""

        async with self._sessions() as session:
            daily_session, project = await self._session_by_message(session, message_id)
            assignment = await session.scalar(
                select(DailyAssignment).where(
                    DailyAssignment.session_id == daily_session.id,
                    DailyAssignment.discord_user_id == user_id,
                )
            )
            if assignment is None:
                raise AuthorizationError("Você não participa desta sessão de daily.")
            if daily_session.status != SessionStatus.OPEN:
                raise ConflictError("Esta daily já está encerrada.")
            if assignment.status == AssignmentStatus.ANSWERED:
                raise ConflictError("Você já respondeu esta daily.")

            questions = await self._questions(session, daily_session.id)
            return DailyResponseForm(
                message_id=message_id,
                project_name=project.name,
                local_date=daily_session.session_date,
                questions=tuple(
                    QuestionPrompt(
                        id=question.id,
                        text=question.text,
                        position=question.position,
                        required=question.required,
                    )
                    for question in questions
                ),
            )

    async def submit_response(
        self, *, message_id: int, user_id: int, answers: Mapping[int, str]
    ) -> DailyPanel:
        """Persist one private response and return the answer-free public panel."""

        async with self._sessions() as session, session.begin():
            daily_session, project = await self._session_by_message(session, message_id)
            if daily_session.status != SessionStatus.OPEN:
                raise ConflictError("Esta daily já está encerrada.")
            assignment = await session.scalar(
                select(DailyAssignment).where(
                    DailyAssignment.session_id == daily_session.id,
                    DailyAssignment.discord_user_id == user_id,
                )
            )
            if assignment is None:
                raise AuthorizationError("Você não participa desta sessão de daily.")
            if assignment.status == AssignmentStatus.ANSWERED:
                raise ConflictError("Você já respondeu esta daily.")

            questions = await self._questions(session, daily_session.id)
            question_ids = {question.id for question in questions}
            if set(answers) != question_ids:
                raise ValidationError("Responda o formulário completo desta daily.")
            clean_answers = {question_id: value.strip() for question_id, value in answers.items()}
            if any(question.required and not clean_answers[question.id] for question in questions):
                raise ValidationError("Preencha todas as respostas obrigatórias.")

            session.add_all(
                [
                    DailyAnswer(
                        assignment_id=assignment.id,
                        question_snapshot_id=question.id,
                        content=clean_answers[question.id],
                    )
                    for question in questions
                ]
            )
            assignment.status = AssignmentStatus.ANSWERED
            assignment.answered_at = self._now()
            await session.flush()
            return await self._panel(session, daily_session, project.name)

    async def _authorized_guild(self, session: AsyncSession, actor: ActorContext) -> Guild:
        guild = await ensure_guild_record(
            session,
            discord_guild_id=actor.guild_id,
            guild_name=actor.guild_name,
            timezone=self._timezone,
        )
        await authorize_admin(session, guild=guild, actor=actor)
        return guild

    @staticmethod
    async def _project(session: AsyncSession, guild: Guild, slug: str) -> Project:
        project = await session.scalar(
            select(Project).where(
                Project.guild_id == guild.id,
                Project.slug == slug.strip().lower(),
            )
        )
        if project is None:
            raise NotFoundError("Projeto não encontrado neste servidor.")
        return project

    @staticmethod
    async def _session_by_message(
        session: AsyncSession, message_id: int
    ) -> tuple[DailySession, Project]:
        row = (
            await session.execute(
                select(DailySession, Project)
                .join(Project, Project.id == DailySession.project_id)
                .where(DailySession.message_id == message_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Sessão de daily não encontrada para esta mensagem.")
        return row[0], row[1]

    @staticmethod
    async def _questions(session: AsyncSession, session_id: int) -> list[DailyQuestionSnapshot]:
        return list(
            (
                await session.scalars(
                    select(DailyQuestionSnapshot)
                    .where(DailyQuestionSnapshot.session_id == session_id)
                    .order_by(DailyQuestionSnapshot.position)
                )
            ).all()
        )

    @staticmethod
    async def _panel(
        session: AsyncSession, daily_session: DailySession, project_name: str
    ) -> DailyPanel:
        assignments = (
            await session.scalars(
                select(DailyAssignment)
                .where(DailyAssignment.session_id == daily_session.id)
                .order_by(DailyAssignment.display_name, DailyAssignment.id)
            )
        ).all()
        return DailyPanel(
            session_id=daily_session.id,
            project_name=project_name,
            local_date=daily_session.session_date,
            participants=tuple(
                DailyParticipant(
                    user_id=assignment.discord_user_id,
                    display_name=assignment.display_name,
                    answered=assignment.status == AssignmentStatus.ANSWERED,
                )
                for assignment in assignments
            ),
        )

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _open_project_session(
    session: AsyncSession,
    *,
    guild: Guild,
    project: Project,
    local_date: date,
    opened_at: datetime,
) -> OpenedDaily:
    """Create or reuse one project session inside the caller's transaction."""

    daily_session = await session.scalar(
        select(DailySession).where(
            DailySession.project_id == project.id,
            DailySession.session_date == local_date,
        )
    )
    if daily_session is not None:
        return OpenedDaily(
            panel=await DailyService._panel(session, daily_session, project.name),
            channel_id=project.discord_channel_id,
            message_id=daily_session.message_id,
        )

    memberships = (
        await session.scalars(
            select(ProjectMembership)
            .where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.left_at.is_(None),
            )
            .order_by(ProjectMembership.display_name, ProjectMembership.id)
        )
    ).all()
    if not memberships:
        raise ValidationError("Adicione ao menos um membro ativo antes de abrir a daily.")

    questions = (
        await session.scalars(
            select(DailyQuestion)
            .where(DailyQuestion.guild_id == guild.id, DailyQuestion.active.is_(True))
            .order_by(DailyQuestion.position)
        )
    ).all()
    if not questions:
        raise ValidationError("Não há perguntas ativas para esta daily.")
    if len(questions) > 5:
        raise ValidationError("A daily possui mais de cinco perguntas e não cabe em um modal.")

    daily_session = DailySession(
        project_id=project.id,
        session_date=local_date,
        status=SessionStatus.OPEN,
        opened_at=opened_at,
        closed_at=None,
        message_id=None,
    )
    session.add(daily_session)
    await session.flush()
    session.add_all(
        [
            DailyAssignment(
                session_id=daily_session.id,
                discord_user_id=membership.discord_user_id,
                display_name=membership.display_name,
                status=AssignmentStatus.PENDING,
                answered_at=None,
            )
            for membership in memberships
        ]
    )
    session.add_all(
        [
            DailyQuestionSnapshot(
                session_id=daily_session.id,
                text=question.text,
                position=question.position,
                required=question.required,
            )
            for question in questions
        ]
    )
    await session.flush()
    return OpenedDaily(
        panel=await DailyService._panel(session, daily_session, project.name),
        channel_id=project.discord_channel_id,
        message_id=None,
    )
