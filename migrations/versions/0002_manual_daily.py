"""Add guild configuration, projects, memberships, and manual daily tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_manual_daily"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    """Create the complete persistence model for manual dailies."""

    op.create_table(
        "guilds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_guilds"),
        sa.UniqueConstraint("discord_guild_id", name="uq_guilds_discord_guild_id"),
    )
    op.create_table(
        "guild_settings",
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'America/Belem'"),
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_guild_settings_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("guild_id", name="pk_guild_settings"),
    )
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], name="fk_admin_roles_guild_id_guilds", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_roles"),
        sa.UniqueConstraint(
            "guild_id", "discord_role_id", name="uq_admin_roles_guild_discord_role"
        ),
    )
    op.create_table(
        "daily_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("position > 0", name="ck_daily_questions_positive_position"),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_daily_questions_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_questions"),
        sa.UniqueConstraint("guild_id", "position", name="uq_daily_questions_guild_position"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=8), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        sa.Column("daily_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_projects_status"),
        sa.ForeignKeyConstraint(
            ["guild_id"], ["guilds.id"], name="fk_projects_guild_id_guilds", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("guild_id", "slug", name="uq_projects_guild_slug"),
    )
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_memberships_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_memberships"),
    )
    op.create_index(
        "uq_project_memberships_active_user",
        "project_memberships",
        ["project_id", "discord_user_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )
    op.create_table(
        "daily_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=6), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_daily_sessions_status"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_daily_sessions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_sessions"),
        sa.UniqueConstraint("message_id", name="uq_daily_sessions_message_id"),
        sa.UniqueConstraint("project_id", "session_date", name="uq_daily_sessions_project_date"),
    )
    op.create_table(
        "daily_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "status", sa.String(length=8), server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ANSWERED', 'ABSENT')",
            name="ck_daily_assignments_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["daily_sessions.id"],
            name="fk_daily_assignments_session_id_daily_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_assignments"),
        sa.UniqueConstraint(
            "session_id", "discord_user_id", name="uq_daily_assignments_session_user"
        ),
    )
    op.create_table(
        "daily_question_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("position > 0", name="ck_daily_question_snapshots_positive_position"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["daily_sessions.id"],
            name="fk_daily_question_snapshots_session_id_daily_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_question_snapshots"),
        sa.UniqueConstraint(
            "session_id",
            "position",
            name="uq_daily_question_snapshots_session_position",
        ),
    )
    op.create_table(
        "daily_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("question_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["daily_assignments.id"],
            name="fk_daily_answers_assignment_id_daily_assignments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_snapshot_id"],
            ["daily_question_snapshots.id"],
            name="fk_daily_answers_question_snapshot_id_daily_question_snapshots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_answers"),
        sa.UniqueConstraint(
            "assignment_id",
            "question_snapshot_id",
            name="uq_daily_answers_assignment_question",
        ),
    )


def downgrade() -> None:
    """Remove all manual daily persistence tables."""

    op.drop_table("daily_answers")
    op.drop_table("daily_question_snapshots")
    op.drop_table("daily_assignments")
    op.drop_table("daily_sessions")
    op.drop_index("uq_project_memberships_active_user", table_name="project_memberships")
    op.drop_table("project_memberships")
    op.drop_table("projects")
    op.drop_table("daily_questions")
    op.drop_table("admin_roles")
    op.drop_table("guild_settings")
    op.drop_table("guilds")
