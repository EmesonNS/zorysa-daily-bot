"""SQLAlchemy mappings for guild configuration and manual daily sessions."""

from datetime import date, datetime, time
from typing import Annotated

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import AssignmentStatus, NotificationKind, ProjectStatus, SessionStatus


class Base(DeclarativeBase):
    """Declarative base with deterministic constraint naming."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


Timestamp = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now()),
]
PrimaryKey = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True)]
DiscordId = Annotated[int, mapped_column(BigInteger, nullable=False)]


class TimestampMixin:
    """Provide audit timestamps to mutable records."""

    created_at: Mapped[Timestamp]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Guild(TimestampMixin, Base):
    """A Discord guild known by the bot."""

    __tablename__ = "guilds"

    id: Mapped[PrimaryKey]
    discord_guild_id: Mapped[DiscordId] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    settings: Mapped["GuildSettings"] = relationship(
        back_populates="guild", cascade="all, delete-orphan", uselist=False
    )
    admin_roles: Mapped[list["AdminRole"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    questions: Mapped[list["DailyQuestion"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    execution_days: Mapped[list["GuildExecutionDay"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    report_channels: Mapped[list["ReportChannel"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )
    report_deliveries: Mapped[list["DailyReportDelivery"]] = relationship(
        back_populates="guild", cascade="all, delete-orphan"
    )


class GuildSettings(TimestampMixin, Base):
    """Per-guild operational settings."""

    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=sql_text("'America/Belem'")
    )
    daily_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("true")
    )
    daily_open_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=sql_text("'09:00:00'")
    )
    first_reminder_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=sql_text("'10:30:00'")
    )
    last_reminder_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=sql_text("'11:30:00'")
    )
    daily_close_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=sql_text("'12:00:00'")
    )
    daily_report_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=sql_text("'12:10:00'")
    )

    guild: Mapped[Guild] = relationship(back_populates="settings")


class GuildExecutionDay(Base):
    """Weekday on which one guild runs automatic dailies."""

    __tablename__ = "guild_execution_days"
    __table_args__ = (CheckConstraint("weekday >= 0 AND weekday <= 6", name="valid_weekday"),)

    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    guild: Mapped[Guild] = relationship(back_populates="execution_days")


class ReportChannel(TimestampMixin, Base):
    """Discord channel configured to receive one or more report types."""

    __tablename__ = "report_channels"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "discord_channel_id",
            name="uq_report_channels_guild_discord_channel",
        ),
    )

    id: Mapped[PrimaryKey]
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"))
    discord_channel_id: Mapped[DiscordId]
    daily_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("true")
    )
    weekly_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )
    monthly_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )

    guild: Mapped[Guild] = relationship(back_populates="report_channels")


class DailyReportDelivery(TimestampMixin, Base):
    """Idempotent publication marker for one guild, local date, and channel."""

    __tablename__ = "daily_report_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "report_date",
            "discord_channel_id",
            name="uq_daily_report_deliveries_guild_date_channel",
        ),
    )

    id: Mapped[PrimaryKey]
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"))
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    discord_channel_id: Mapped[DiscordId]
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_count: Mapped[int | None] = mapped_column(Integer)

    guild: Mapped[Guild] = relationship(back_populates="report_deliveries")


class AdminRole(TimestampMixin, Base):
    """Discord role allowed to administer one guild."""

    __tablename__ = "admin_roles"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "discord_role_id",
            name="uq_admin_roles_guild_discord_role",
        ),
    )

    id: Mapped[PrimaryKey]
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"))
    discord_role_id: Mapped[DiscordId]

    guild: Mapped[Guild] = relationship(back_populates="admin_roles")


class DailyQuestion(TimestampMixin, Base):
    """An active or historical question configured for a guild."""

    __tablename__ = "daily_questions"
    __table_args__ = (
        UniqueConstraint("guild_id", "position", name="uq_daily_questions_guild_position"),
        CheckConstraint("position > 0", name="positive_position"),
    )

    id: Mapped[PrimaryKey]
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))

    guild: Mapped[Guild] = relationship(back_populates="questions")


class Project(TimestampMixin, Base):
    """A project whose daily is published in a Discord channel."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("guild_id", "slug", name="uq_projects_guild_slug"),)

    id: Mapped[PrimaryKey]
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    discord_channel_id: Mapped[DiscordId]
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        server_default=sql_text("'ACTIVE'"),
    )
    daily_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("true")
    )

    guild: Mapped[Guild] = relationship(back_populates="projects")
    memberships: Mapped[list["ProjectMembership"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["DailySession"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMembership(TimestampMixin, Base):
    """Historical membership of one Discord user in a project."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        Index(
            "uq_project_memberships_active_user",
            "project_id",
            "discord_user_id",
            unique=True,
            postgresql_where=sql_text("left_at IS NULL"),
        ),
    )

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    discord_user_id: Mapped[DiscordId]
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    joined_at: Mapped[Timestamp]
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="memberships")


class DailySession(TimestampMixin, Base):
    """One manually opened daily for a project and local date."""

    __tablename__ = "daily_sessions"
    __table_args__ = (
        UniqueConstraint("project_id", "session_date", name="uq_daily_sessions_project_date"),
        UniqueConstraint("message_id", name="uq_daily_sessions_message_id"),
    )

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(
            SessionStatus,
            name="status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        server_default=sql_text("'OPEN'"),
    )
    opened_at: Mapped[Timestamp]
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_id: Mapped[int | None] = mapped_column(BigInteger)

    project: Mapped[Project] = relationship(back_populates="sessions")
    assignments: Mapped[list["DailyAssignment"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    question_snapshots: Mapped[list["DailyQuestionSnapshot"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["DailyNotification"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class DailyNotification(TimestampMixin, Base):
    """Persisted delivery marker for an idempotent daily reminder."""

    __tablename__ = "daily_notifications"
    __table_args__ = (
        UniqueConstraint("session_id", "kind", name="uq_daily_notifications_session_kind"),
    )

    id: Mapped[PrimaryKey]
    session_id: Mapped[int] = mapped_column(ForeignKey("daily_sessions.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(
            NotificationKind,
            name="kind",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[DailySession] = relationship(back_populates="notifications")


class DailyAssignment(TimestampMixin, Base):
    """Participant snapshot for one daily session."""

    __tablename__ = "daily_assignments"
    __table_args__ = (
        UniqueConstraint("session_id", "discord_user_id", name="uq_daily_assignments_session_user"),
        CheckConstraint(
            "(status = 'EXCUSED' AND excused_at IS NOT NULL "
            "AND excused_by_user_id IS NOT NULL AND excuse_reason IS NOT NULL) "
            "OR (status <> 'EXCUSED' AND excused_at IS NULL "
            "AND excused_by_user_id IS NULL AND excuse_reason IS NULL)",
            name="excused_metadata",
        ),
    )

    id: Mapped[PrimaryKey]
    session_id: Mapped[int] = mapped_column(ForeignKey("daily_sessions.id", ondelete="CASCADE"))
    discord_user_id: Mapped[DiscordId]
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(
            AssignmentStatus,
            name="status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        server_default=sql_text("'PENDING'"),
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    excused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    excused_by_user_id: Mapped[int | None] = mapped_column(BigInteger)
    excuse_reason: Mapped[str | None] = mapped_column(Text)

    session: Mapped[DailySession] = relationship(back_populates="assignments")
    answers: Mapped[list["DailyAnswer"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class DailyQuestionSnapshot(TimestampMixin, Base):
    """Immutable question copy attached to an opened session."""

    __tablename__ = "daily_question_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "position",
            name="uq_daily_question_snapshots_session_position",
        ),
        CheckConstraint("position > 0", name="positive_position"),
    )

    id: Mapped[PrimaryKey]
    session_id: Mapped[int] = mapped_column(ForeignKey("daily_sessions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)

    session: Mapped[DailySession] = relationship(back_populates="question_snapshots")
    answers: Mapped[list["DailyAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class DailyAnswer(TimestampMixin, Base):
    """Private answer submitted for one assignment and question snapshot."""

    __tablename__ = "daily_answers"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "question_snapshot_id",
            name="uq_daily_answers_assignment_question",
        ),
    )

    id: Mapped[PrimaryKey]
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("daily_assignments.id", ondelete="CASCADE")
    )
    question_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("daily_question_snapshots.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    assignment: Mapped[DailyAssignment] = relationship(back_populates="answers")
    question: Mapped[DailyQuestionSnapshot] = relationship(back_populates="answers")
