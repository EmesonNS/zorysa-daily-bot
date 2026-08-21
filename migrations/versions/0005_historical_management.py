"""Add historical reports and administrative audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_historical_management"
down_revision: str | None = "0004_daily_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Expand report periods and persist append-only audit history."""

    op.add_column(
        "guild_settings",
        sa.Column(
            "weekly_report_weekday",
            sa.SmallInteger(),
            server_default=sa.text("4"),
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "weekly_report_time",
            sa.Time(),
            server_default=sa.text("'12:20:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "monthly_report_time",
            sa.Time(),
            server_default=sa.text("'12:20:00'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "valid_weekly_report_weekday",
        "guild_settings",
        "weekly_report_weekday >= 0 AND weekly_report_weekday <= 6",
    )

    op.rename_table("daily_report_deliveries", "report_deliveries")
    op.execute(
        "ALTER TABLE report_deliveries RENAME CONSTRAINT "
        "pk_daily_report_deliveries TO pk_report_deliveries"
    )
    op.execute(
        "ALTER TABLE report_deliveries RENAME CONSTRAINT "
        "fk_daily_report_deliveries_guild_id_guilds "
        "TO fk_report_deliveries_guild_id_guilds"
    )
    op.drop_constraint(
        "uq_daily_report_deliveries_guild_date_channel",
        "report_deliveries",
        type_="unique",
    )
    op.alter_column(
        "report_deliveries",
        "report_date",
        new_column_name="period_start",
    )
    op.add_column(
        "report_deliveries",
        sa.Column(
            "kind",
            sa.String(length=7),
            server_default=sa.text("'DAILY'"),
            nullable=False,
        ),
    )
    op.add_column(
        "report_deliveries",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    op.execute("UPDATE report_deliveries SET period_end = period_start")
    op.alter_column("report_deliveries", "period_end", nullable=False)
    op.create_check_constraint(
        "report_kind",
        "report_deliveries",
        "kind IN ('DAILY', 'WEEKLY', 'MONTHLY')",
    )
    op.create_check_constraint(
        "valid_period",
        "report_deliveries",
        "period_end >= period_start",
    )
    op.create_unique_constraint(
        "uq_report_deliveries_guild_kind_period_channel",
        "report_deliveries",
        ["guild_id", "kind", "period_start", "period_end", "discord_channel_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guilds.id"],
            name="fk_audit_events_guild_id_guilds",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.execute(
        "CREATE INDEX ix_audit_events_guild_occurred_id "
        "ON audit_events (guild_id, occurred_at DESC, id DESC)"
    )
    op.create_index(
        "ix_audit_events_guild_actor",
        "audit_events",
        ["guild_id", "actor_user_id"],
    )
    op.create_index(
        "ix_audit_events_guild_action",
        "audit_events",
        ["guild_id", "action"],
    )


def downgrade() -> None:
    """Remove M4 history while retaining compatible daily deliveries."""

    op.drop_table("audit_events")

    op.execute("DELETE FROM report_deliveries WHERE kind <> 'DAILY'")
    op.drop_constraint(
        "uq_report_deliveries_guild_kind_period_channel",
        "report_deliveries",
        type_="unique",
    )
    op.drop_constraint(
        "valid_period",
        "report_deliveries",
        type_="check",
    )
    op.drop_constraint(
        "report_kind",
        "report_deliveries",
        type_="check",
    )
    op.drop_column("report_deliveries", "period_end")
    op.drop_column("report_deliveries", "kind")
    op.alter_column(
        "report_deliveries",
        "period_start",
        new_column_name="report_date",
    )
    op.create_unique_constraint(
        "uq_daily_report_deliveries_guild_date_channel",
        "report_deliveries",
        ["guild_id", "report_date", "discord_channel_id"],
    )
    op.execute(
        "ALTER TABLE report_deliveries RENAME CONSTRAINT "
        "fk_report_deliveries_guild_id_guilds "
        "TO fk_daily_report_deliveries_guild_id_guilds"
    )
    op.execute(
        "ALTER TABLE report_deliveries RENAME CONSTRAINT "
        "pk_report_deliveries TO pk_daily_report_deliveries"
    )
    op.rename_table("report_deliveries", "daily_report_deliveries")

    op.drop_constraint(
        "valid_weekly_report_weekday",
        "guild_settings",
        type_="check",
    )
    op.drop_column("guild_settings", "monthly_report_time")
    op.drop_column("guild_settings", "weekly_report_time")
    op.drop_column("guild_settings", "weekly_report_weekday")
