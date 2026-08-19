"""Add guild schedules and automatic daily notification markers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_automatic_daily"
down_revision: str | None = "0002_manual_daily"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist automatic daily configuration and delivery state."""

    op.add_column(
        "guild_settings",
        sa.Column("daily_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "daily_open_time",
            sa.Time(),
            server_default=sa.text("'09:00:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "first_reminder_time",
            sa.Time(),
            server_default=sa.text("'10:30:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "last_reminder_time",
            sa.Time(),
            server_default=sa.text("'11:30:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "daily_close_time",
            sa.Time(),
            server_default=sa.text("'12:00:00'"),
            nullable=False,
        ),
    )

    op.create_table(
        "guild_execution_days",
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_guild_execution_days_valid_weekday",
        ),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_guild_execution_days_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("guild_id", "weekday", name="pk_guild_execution_days"),
    )
    op.execute(
        sa.text(
            "INSERT INTO guild_execution_days (guild_id, weekday) "
            "SELECT guilds.id, days.weekday FROM guilds "
            "CROSS JOIN generate_series(0, 4) AS days(weekday) "
            "ON CONFLICT DO NOTHING"
        )
    )

    op.drop_constraint("ck_daily_assignments_status", "daily_assignments", type_="check")
    op.alter_column(
        "daily_assignments",
        "status",
        existing_type=sa.String(length=8),
        type_=sa.String(length=12),
        existing_nullable=False,
        existing_server_default=sa.text("'PENDING'"),
    )
    op.create_check_constraint(
        "ck_daily_assignments_status",
        "daily_assignments",
        "status IN ('PENDING', 'ANSWERED', 'ABSENT', 'NOT_ANSWERED')",
    )

    op.create_table(
        "daily_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=14), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('FIRST_REMINDER', 'LAST_REMINDER')",
            name="ck_daily_notifications_kind",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["daily_sessions.id"],
            name="fk_daily_notifications_session_id_daily_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_notifications"),
        sa.UniqueConstraint("session_id", "kind", name="uq_daily_notifications_session_kind"),
    )


def downgrade() -> None:
    """Remove automatic scheduling while preserving compatible assignment data."""

    op.drop_table("daily_notifications")

    op.execute(
        sa.text("UPDATE daily_assignments SET status = 'PENDING' WHERE status = 'NOT_ANSWERED'")
    )
    op.drop_constraint("ck_daily_assignments_status", "daily_assignments", type_="check")
    op.alter_column(
        "daily_assignments",
        "status",
        existing_type=sa.String(length=12),
        type_=sa.String(length=8),
        existing_nullable=False,
        existing_server_default=sa.text("'PENDING'"),
    )
    op.create_check_constraint(
        "ck_daily_assignments_status",
        "daily_assignments",
        "status IN ('PENDING', 'ANSWERED', 'ABSENT')",
    )

    op.drop_table("guild_execution_days")
    op.drop_column("guild_settings", "daily_close_time")
    op.drop_column("guild_settings", "last_reminder_time")
    op.drop_column("guild_settings", "first_reminder_time")
    op.drop_column("guild_settings", "daily_open_time")
    op.drop_column("guild_settings", "daily_enabled")
