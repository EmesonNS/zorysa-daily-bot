from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.domain.enums import (
    AssignmentStatus,
    NotificationKind,
    ProjectStatus,
    SessionStatus,
)
from app.infrastructure.database.models import (
    Base,
    DailyAssignment,
    GuildExecutionDay,
    GuildSettings,
    ProjectMembership,
    ReportChannel,
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
        "daily_report_deliveries",
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


def test_report_delivery_is_unique_per_guild_date_and_channel() -> None:
    constraints = Base.metadata.tables["daily_report_deliveries"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_daily_report_deliveries_guild_date_channel"
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
