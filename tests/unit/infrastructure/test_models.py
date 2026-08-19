from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.domain.enums import AssignmentStatus, ProjectStatus, SessionStatus
from app.infrastructure.database.models import Base, ProjectMembership


def test_manual_daily_metadata_contains_all_expected_tables() -> None:
    assert set(Base.metadata.tables) == {
        "admin_roles",
        "daily_answers",
        "daily_assignments",
        "daily_question_snapshots",
        "daily_questions",
        "daily_sessions",
        "guild_settings",
        "guilds",
        "project_memberships",
        "projects",
    }


def test_domain_enums_use_stable_persisted_values() -> None:
    assert [status.value for status in ProjectStatus] == ["ACTIVE", "ARCHIVED"]
    assert [status.value for status in SessionStatus] == ["OPEN", "CLOSED"]
    assert [status.value for status in AssignmentStatus] == [
        "PENDING",
        "ANSWERED",
        "ABSENT",
    ]


def test_tenant_and_snapshot_uniqueness_is_declared_in_metadata() -> None:
    expected_constraints = {
        "admin_roles": "uq_admin_roles_guild_discord_role",
        "daily_answers": "uq_daily_answers_assignment_question",
        "daily_assignments": "uq_daily_assignments_session_user",
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
