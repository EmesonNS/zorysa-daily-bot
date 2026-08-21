"""Guild-scoped administration of configurable daily questions."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.dto import ActorContext, QuestionSummary
from app.application.errors import ConflictError, NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AuditAction
from app.infrastructure.database.models import DailyQuestion, Guild

MAX_ACTIVE_QUESTIONS = 5
MAX_QUESTION_TEXT_LENGTH = 1000


class QuestionService:
    """Maintain ordered questions without mutating historical snapshots."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone

    async def list_questions(self, *, actor: ActorContext) -> tuple[QuestionSummary, ...]:
        """List active and inactive questions in presentation order."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            questions = await self._ordered_questions(session, guild.id)
            return tuple(self._summary(question) for question in questions)

    async def add_question(
        self, *, actor: ActorContext, text: str, required: bool
    ) -> QuestionSummary:
        """Append one active question while respecting the Discord modal limit."""

        clean_text = self._clean_text(text)
        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                questions = await self._ordered_questions(session, guild.id, lock=True)
                self._ensure_can_activate(questions)
                question = DailyQuestion(
                    guild_id=guild.id,
                    text=clean_text,
                    position=max((item.position for item in questions), default=0) + 1,
                    required=required,
                    active=True,
                )
                session.add(question)
                await session.flush()
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.QUESTION_ADDED,
                    target_type="daily_question",
                    target_id=question.id,
                    details={
                        "position": question.position,
                        "required": question.required,
                        "active": question.active,
                    },
                )
                return self._summary(question)
        except IntegrityError as error:
            raise ConflictError("As perguntas foram alteradas; tente novamente.") from error

    async def edit_question(
        self,
        *,
        actor: ActorContext,
        question_id: int,
        text: str,
        required: bool,
    ) -> QuestionSummary:
        """Edit only future-session configuration for one guild question."""

        clean_text = self._clean_text(text)
        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            question = await self._question(session, guild.id, question_id, lock=True)
            question.text = clean_text
            question.required = required
            await session.flush()
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.QUESTION_EDITED,
                target_type="daily_question",
                target_id=question.id,
                details={"required": question.required, "active": question.active},
            )
            return self._summary(question)

    async def move_question(
        self, *, actor: ActorContext, question_id: int, position: int
    ) -> tuple[QuestionSummary, ...]:
        """Move one question and compact all guild positions atomically."""

        if position <= 0:
            raise ValidationError("Informe uma posição válida a partir de 1.")
        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                questions = await self._ordered_questions(session, guild.id, lock=True)
                if position > len(questions):
                    raise ValidationError(f"A posição deve estar entre 1 e {len(questions)}.")
                moving = next((item for item in questions if item.id == question_id), None)
                if moving is None:
                    raise NotFoundError("Pergunta não encontrada neste servidor.")
                previous_position = moving.position
                reordered = [item for item in questions if item.id != question_id]
                reordered.insert(position - 1, moving)

                offset = max((item.position for item in questions), default=0) + len(questions) + 1
                await session.execute(
                    update(DailyQuestion)
                    .where(DailyQuestion.guild_id == guild.id)
                    .values(position=DailyQuestion.position + offset),
                    execution_options={"synchronize_session": False},
                )
                for new_position, question in enumerate(reordered, start=1):
                    question.position = new_position
                await session.flush()
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.QUESTION_MOVED,
                    target_type="daily_question",
                    target_id=moving.id,
                    details={"previous_position": previous_position, "position": position},
                )
                return tuple(self._summary(question) for question in reordered)
        except IntegrityError as error:
            raise ConflictError("As perguntas foram reordenadas em outra interação.") from error

    async def set_question_active(
        self, *, actor: ActorContext, question_id: int, active: bool
    ) -> QuestionSummary:
        """Activate or deactivate a question while preserving the 1..5 bound."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            questions = await self._ordered_questions(session, guild.id, lock=True)
            question = next((item for item in questions if item.id == question_id), None)
            if question is None:
                raise NotFoundError("Pergunta não encontrada neste servidor.")
            if question.active == active:
                return self._summary(question)

            active_count = sum(item.active for item in questions)
            if active and active_count >= MAX_ACTIVE_QUESTIONS:
                raise ConflictError("A daily pode ter no máximo cinco perguntas ativas.")
            if not active and active_count <= 1:
                raise ConflictError("A daily deve manter ao menos uma pergunta ativa.")
            question.active = active
            await session.flush()
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=(
                    AuditAction.QUESTION_ACTIVATED if active else AuditAction.QUESTION_DEACTIVATED
                ),
                target_type="daily_question",
                target_id=question.id,
                details={"active": active},
            )
            return self._summary(question)

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
    async def _ordered_questions(
        session: AsyncSession, guild_id: int, *, lock: bool = False
    ) -> list[DailyQuestion]:
        statement = (
            select(DailyQuestion)
            .where(DailyQuestion.guild_id == guild_id)
            .order_by(DailyQuestion.position, DailyQuestion.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await session.scalars(statement)).all())

    @staticmethod
    async def _question(
        session: AsyncSession, guild_id: int, question_id: int, *, lock: bool
    ) -> DailyQuestion:
        statement = select(DailyQuestion).where(
            DailyQuestion.guild_id == guild_id,
            DailyQuestion.id == question_id,
        )
        if lock:
            statement = statement.with_for_update()
        question = await session.scalar(statement)
        if question is None:
            raise NotFoundError("Pergunta não encontrada neste servidor.")
        return question

    @staticmethod
    def _clean_text(text: str) -> str:
        clean_text = text.strip()
        if not clean_text or len(clean_text) > MAX_QUESTION_TEXT_LENGTH:
            raise ValidationError("Informe um texto de pergunta com até 1000 caracteres.")
        return clean_text

    @staticmethod
    def _ensure_can_activate(questions: list[DailyQuestion]) -> None:
        if sum(question.active for question in questions) >= MAX_ACTIVE_QUESTIONS:
            raise ConflictError("A daily pode ter no máximo cinco perguntas ativas.")

    @staticmethod
    def _summary(question: DailyQuestion) -> QuestionSummary:
        return QuestionSummary(
            id=question.id,
            text=question.text,
            position=question.position,
            required=question.required,
            active=question.active,
        )
