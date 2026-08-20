"""Data contracts for the manual daily workflow."""

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums import AssignmentStatus, NotificationKind, SessionStatus


@dataclass(frozen=True, slots=True)
class DailyParticipant:
    """Participant state shown on the public daily panel."""

    user_id: int
    display_name: str
    status: AssignmentStatus

    @property
    def answered(self) -> bool:
        """Preserve the public answered flag used by existing presentation flows."""

        return self.status == AssignmentStatus.ANSWERED


@dataclass(frozen=True, slots=True)
class DailyPanel:
    """Public, answer-free representation of a daily session."""

    session_id: int
    project_name: str
    local_date: date
    status: SessionStatus
    participants: tuple[DailyParticipant, ...]


@dataclass(frozen=True, slots=True)
class QuestionPrompt:
    """Snapshotted question safe to render in a private modal."""

    id: int
    text: str
    position: int
    required: bool


@dataclass(frozen=True, slots=True)
class DailyResponseForm:
    """Information required to build one member's response modal."""

    message_id: int
    project_name: str
    local_date: date
    questions: tuple[QuestionPrompt, ...]


@dataclass(frozen=True, slots=True)
class OpenedDaily:
    """Session state plus its Discord publication target."""

    panel: DailyPanel
    channel_id: int
    message_id: int | None


@dataclass(frozen=True, slots=True)
class JustifiedDaily:
    """Updated public panel plus the existing Discord publication target."""

    panel: DailyPanel
    channel_id: int
    message_id: int | None


@dataclass(frozen=True, slots=True)
class ReminderRecipient:
    """Pending participant who should be mentioned in one reminder."""

    user_id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class PreparedReminder:
    """Persisted reminder reservation ready for Discord publication."""

    notification_id: int
    session_id: int
    project_name: str
    channel_id: int
    kind: NotificationKind
    recipients: tuple[ReminderRecipient, ...]


@dataclass(frozen=True, slots=True)
class ClosedDaily:
    """Final public panel and Discord target for one closed session."""

    panel: DailyPanel
    channel_id: int
    message_id: int | None
    closed_at: datetime
