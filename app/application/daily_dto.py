"""Data contracts for the manual daily workflow."""

from dataclasses import dataclass
from datetime import date

from app.domain.enums import NotificationKind


@dataclass(frozen=True, slots=True)
class DailyParticipant:
    """Participant state shown on the public daily panel."""

    user_id: int
    display_name: str
    answered: bool


@dataclass(frozen=True, slots=True)
class DailyPanel:
    """Public, answer-free representation of a daily session."""

    session_id: int
    project_name: str
    local_date: date
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
