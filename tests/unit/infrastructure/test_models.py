from datetime import date

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

import app.domain as domain
import app.infrastructure.database as database
from app.domain.enums import (
    AssignmentStatus,
    AuditAction,
    NotificationKind,
    ProjectStatus,
    ReportKind,
    SessionStatus,
)
from app.infrastructure.database.models import (
    AuditEvent,
    Base,
    DailyAssignment,
    GuildExecutionDay,
    GuildSettings,
    ProjectMembership,
    ReportChannel,
    ReportDelivery,
)


def test_manual_daily_metadata_contains_all_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "admin_roles",
        "daily_answers",
        "daily_assignments",
        "daily_notifications",
        "daily_question_snapshots",
        "daily_questions",
        "daily_sessions",
        "guild_settings",
        "guild_execution_days",
        "guilds",
        "project_memberships",
        "projects",
        "report_channels",
        "report_deliveries",
        "audit_events",
    }


def test_domain_enums_use_stable_persisted_values() -> None:
    assert [status.value for status in ProjectStatus] == ["ACTIVE", "ARCHIVED"]
    assert [status.value for status in SessionStatus] == ["OPEN", "CLOSED"]
    assert [status.value for status in AssignmentStatus] == [
        "PENDING",
        "ANSWERED",
        "ABSENT",
        "NOT_ANSWERED",
        "EXCUSED",
    ]
    assert [kind.value for kind in NotificationKind] == [
        "FIRST_REMINDER",
        "LAST_REMINDER",
    ]


def test_tenant_and_snapshot_uniqueness_is_declared_in_metadata() -> None:
    expected_constraints = {
        "admin_roles": "uq_admin_roles_guild_discord_role",
        "daily_answers": "uq_daily_answers_assignment_question",
        "daily_assignments": "uq_daily_assignments_session_user",
        "daily_notifications": "uq_daily_notifications_session_kind",
        "daily_question_snapshots": "uq_daily_question_snapshots_session_position",
        "daily_questions": "uq_daily_questions_guild_position",
        "daily_sessions": "uq_daily_sessions_project_date",
        "projects": "uq_projects_guild_slug",
    }

    for table_name, constraint_name in expected_constraints.items():
        constraints = Base.metadata.tables[table_name].constraints
        assert any(
            isinstance(constraint, UniqueConstraint) and constraint.name == constraint_name
            for constraint in constraints
        )


def test_model_state_columns_have_database_check_constraints() -> None:
    assert any(
        isinstance(constraint, CheckConstraint) and constraint.name == "ck_projects_status"
        for constraint in Base.metadata.tables["projects"].constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint) and constraint.name == "ck_daily_sessions_status"
        for constraint in Base.metadata.tables["daily_sessions"].constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint) and constraint.name == "ck_daily_assignments_status"
        for constraint in Base.metadata.tables["daily_assignments"].constraints
    )


def test_membership_has_partial_unique_index_for_active_participant() -> None:
    index = next(
        index
        for index in ProjectMembership.__table__.indexes
        if index.name == "uq_project_memberships_active_user"
    )

    assert index.unique is True
    predicate = index.dialect_options["postgresql"]["where"]
    assert str(predicate.compile(dialect=postgresql.dialect())) == "left_at IS NULL"


def test_guild_schedule_has_expected_defaults_and_column_types() -> None:
    columns = GuildSettings.__table__.columns

    assert str(columns.daily_enabled.server_default.arg) == "true"
    assert str(columns.daily_open_time.server_default.arg) == "'09:00:00'"
    assert str(columns.first_reminder_time.server_default.arg) == "'10:30:00'"
    assert str(columns.last_reminder_time.server_default.arg) == "'11:30:00'"
    assert str(columns.daily_close_time.server_default.arg) == "'12:00:00'"
    for name in (
        "daily_open_time",
        "first_reminder_time",
        "last_reminder_time",
        "daily_close_time",
    ):
        assert type(columns[name].type).__name__ == "Time"


def test_execution_day_uses_composite_key_and_valid_weekday_check() -> None:
    table = GuildExecutionDay.__table__

    assert {column.name for column in table.primary_key.columns} == {"guild_id", "weekday"}
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_guild_execution_days_valid_weekday"
        and str(constraint.sqltext) == "weekday >= 0 AND weekday <= 6"
        for constraint in table.constraints
    )


def test_report_channel_is_unique_per_guild() -> None:
    constraints = Base.metadata.tables["report_channels"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_report_channels_guild_discord_channel"
        for constraint in constraints
    )


def test_report_delivery_is_unique_per_kind_period_and_channel() -> None:
    constraints = Base.metadata.tables["report_deliveries"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_report_deliveries_guild_kind_period_channel"
        for constraint in constraints
    )


def test_excused_assignment_requires_complete_metadata() -> None:
    constraint = next(
        constraint
        for constraint in DailyAssignment.__table__.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_daily_assignments_excused_metadata"
    )

    assert "status = 'EXCUSED'" in str(constraint.sqltext)
    assert "excused_at IS NOT NULL" in str(constraint.sqltext)
    assert "excused_by_user_id IS NOT NULL" in str(constraint.sqltext)
    assert "excuse_reason IS NOT NULL" in str(constraint.sqltext)


def test_daily_report_time_has_expected_default_and_type() -> None:
    column = GuildSettings.__table__.columns.daily_report_time

    assert str(column.server_default.arg) == "'12:10:00'"
    assert type(column.type).__name__ == "Time"


def test_report_channel_flags_have_daily_only_defaults() -> None:
    columns = ReportChannel.__table__.columns

    assert str(columns.daily_enabled.server_default.arg) == "true"
    assert str(columns.weekly_enabled.server_default.arg) == "false"
    assert str(columns.monthly_enabled.server_default.arg) == "false"


def test_historical_domain_enums_use_stable_values() -> None:
    assert [kind.value for kind in ReportKind] == ["DAILY", "WEEKLY", "MONTHLY"]
    assert [action.value for action in AuditAction] == [
        "PROJECT_CREATED",
        "PROJECT_EDITED",
        "PROJECT_ARCHIVED",
        "MEMBER_ADDED",
        "MEMBER_REMOVED",
        "MEMBER_LEFT_GUILD",
        "SCHEDULE_UPDATED",
        "QUESTION_ADDED",
        "QUESTION_EDITED",
        "QUESTION_MOVED",
        "QUESTION_ACTIVATED",
        "QUESTION_DEACTIVATED",
        "ADMIN_ROLE_ADDED",
        "ADMIN_ROLE_REMOVED",
        "REPORT_CHANNEL_SAVED",
        "REPORT_CHANNEL_REMOVED",
        "ABSENCE_JUSTIFIED",
        "DAILY_CLOSED_MANUALLY",
        "MANUAL_REPORT_REQUESTED",
    ]


def test_management_schedule_has_expected_defaults_and_constraints() -> None:
    table = GuildSettings.__table__
    columns = table.columns

    assert str(columns.weekly_report_weekday.server_default.arg) == "4"
    assert str(columns.weekly_report_time.server_default.arg) == "'12:20:00'"
    assert str(columns.monthly_report_time.server_default.arg) == "'12:20:00'"
    assert type(columns.weekly_report_time.type).__name__ == "Time"
    assert type(columns.monthly_report_time.type).__name__ == "Time"
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_guild_settings_valid_weekly_report_weekday"
        and str(constraint.sqltext) == ("weekly_report_weekday >= 0 AND weekly_report_weekday <= 6")
        for constraint in table.constraints
    )


def test_report_delivery_declares_kind_period_and_compatibility_alias() -> None:
    table = ReportDelivery.__table__

    assert {
        "kind",
        "period_start",
        "period_end",
        "discord_channel_id",
        "sent_at",
        "page_count",
    }.issubset(table.columns.keys())
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_report_deliveries_valid_period"
        and str(constraint.sqltext) == "period_end >= period_start"
        for constraint in table.constraints
    )
    delivery = database.DailyReportDelivery(report_date=date(2026, 8, 21))
    assert delivery.kind == ReportKind.DAILY
    assert delivery.period_start == date(2026, 8, 21)
    assert delivery.period_end == date(2026, 8, 21)


def test_audit_event_has_safe_typed_columns() -> None:
    columns = AuditEvent.__table__.columns

    assert columns.actor_user_id.nullable is True
    assert columns.target_id.nullable is False
    assert columns.occurred_at.nullable is False
    assert isinstance(columns.details.type, postgresql.JSONB)


def test_audit_event_has_query_indexes() -> None:
    indexes = {index.name: index for index in AuditEvent.__table__.indexes}

    assert {
        "ix_audit_events_guild_occurred_id",
        "ix_audit_events_guild_actor",
        "ix_audit_events_guild_action",
    } <= indexes.keys()


def test_historical_models_and_enums_are_publicly_exported() -> None:
    assert domain.ReportKind is ReportKind
    assert domain.AuditAction is AuditAction
    assert database.ReportDelivery is ReportDelivery
    assert database.AuditEvent is AuditEvent
