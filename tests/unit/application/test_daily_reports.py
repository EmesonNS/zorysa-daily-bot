import pytest

from app.application.daily_reports import calculate_metrics
from app.domain.enums import AssignmentStatus


def test_metrics_distinguish_unique_people_from_expected_assignments() -> None:
    metrics = calculate_metrics(
        project_count=2,
        assignments=(
            (10, AssignmentStatus.ANSWERED),
            (10, AssignmentStatus.NOT_ANSWERED),
            (20, AssignmentStatus.EXCUSED),
        ),
    )

    assert metrics.project_count == 2
    assert metrics.unique_participants == 2
    assert metrics.expected_dailies == 3
    assert metrics.answered == 1
    assert metrics.not_answered == 1
    assert metrics.excused == 1
    assert metrics.response_rate == 50.0


def test_metrics_return_zero_rate_without_valid_denominator() -> None:
    metrics = calculate_metrics(
        project_count=0,
        assignments=((10, AssignmentStatus.EXCUSED),),
    )
    assert metrics.response_rate == 0.0


@pytest.mark.parametrize("status", [AssignmentStatus.PENDING, AssignmentStatus.ABSENT])
def test_metrics_treat_unfinished_states_as_not_answered(status: AssignmentStatus) -> None:
    metrics = calculate_metrics(project_count=1, assignments=((10, status),))
    assert metrics.not_answered == 1
    assert metrics.response_rate == 0.0
