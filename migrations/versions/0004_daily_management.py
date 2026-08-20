"""Add daily management, excused absences, and report delivery state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_daily_management"
down_revision: str | None = "0003_automatic_daily"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist report configuration/delivery and justified absence metadata."""

    op.add_column(
        "guild_settings",
        sa.Column(
            "daily_report_time",
            sa.Time(),
            server_default=sa.text("'12:10:00'"),
            nullable=False,
        ),
    )

    op.add_column(
        "daily_assignments",
        sa.Column("excused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "daily_assignments",
        sa.Column("excused_by_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "daily_assignments",
        sa.Column("excuse_reason", sa.Text(), nullable=True),
    )
    op.drop_constraint("ck_daily_assignments_status", "daily_assignments", type_="check")
    op.create_check_constraint(
        "ck_daily_assignments_status",
        "daily_assignments",
        "status IN ('PENDING', 'ANSWERED', 'ABSENT', 'NOT_ANSWERED', 'EXCUSED')",
    )
    op.create_check_constraint(
        "ck_daily_assignments_excused_metadata",
        "daily_assignments",
        "(status = 'EXCUSED' AND excused_at IS NOT NULL "
        "AND excused_by_user_id IS NOT NULL AND excuse_reason IS NOT NULL) "
        "OR (status <> 'EXCUSED' AND excused_at IS NULL "
        "AND excused_by_user_id IS NULL AND excuse_reason IS NULL)",
    )

    op.create_table(
        "report_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("daily_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("weekly_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("monthly_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_report_channels_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_channels"),
        sa.UniqueConstraint(
            "guild_id",
            "discord_channel_id",
            name="uq_report_channels_guild_discord_channel",
        ),
    )

    op.create_table(
        "daily_report_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_daily_report_deliveries_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_report_deliveries"),
        sa.UniqueConstraint(
            "guild_id",
            "report_date",
            "discord_channel_id",
            name="uq_daily_report_deliveries_guild_date_channel",
        ),
    )


def downgrade() -> None:
    """Remove M3 configuration while retaining compatible daily assignments."""

    op.drop_table("daily_report_deliveries")
    op.drop_table("report_channels")

    op.execute(
        sa.text(
            "UPDATE daily_assignments SET status = 'NOT_ANSWERED', "
            "excused_at = NULL, excused_by_user_id = NULL, excuse_reason = NULL "
            "WHERE status = 'EXCUSED'"
        )
    )
    op.drop_constraint(
        "ck_daily_assignments_excused_metadata",
        "daily_assignments",
        type_="check",
    )
    op.drop_constraint("ck_daily_assignments_status", "daily_assignments", type_="check")
    op.create_check_constraint(
        "ck_daily_assignments_status",
        "daily_assignments",
        "status IN ('PENDING', 'ANSWERED', 'ABSENT', 'NOT_ANSWERED')",
    )
    op.drop_column("daily_assignments", "excuse_reason")
    op.drop_column("daily_assignments", "excused_by_user_id")
    op.drop_column("daily_assignments", "excused_at")
    op.drop_column("guild_settings", "daily_report_time")
