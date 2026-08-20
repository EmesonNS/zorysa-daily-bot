"""Immutable daily report contracts."""

from dataclasses import dataclass
from datetime import date

from app.domain.enums import AssignmentStatus


@dataclass(frozen=True, slots=True)
class DailyReportMetrics:
    project_count: int
    unique_participants: int
    expected_dailies: int
    answered: int
    not_answered: int
    excused: int
    response_rate: float


@dataclass(frozen=True, slots=True)
class DailyReportAnswer:
    question: str
    content: str


@dataclass(frozen=True, slots=True)
class DailyReportParticipant:
    user_id: int
    display_name: str
    status: AssignmentStatus
    answers: tuple[DailyReportAnswer, ...]


@dataclass(frozen=True, slots=True)
class DailyReportProject:
    name: str
    participants: tuple[DailyReportParticipant, ...]


@dataclass(frozen=True, slots=True)
class DailyReport:
    report_date: date
    metrics: DailyReportMetrics
    projects: tuple[DailyReportProject, ...]


@dataclass(frozen=True, slots=True)
class PreparedDailyReport:
    delivery_id: int
    channel_id: int
    report: DailyReport
