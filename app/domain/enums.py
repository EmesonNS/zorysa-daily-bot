"""Stable domain states persisted by the manual daily workflow."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    """Lifecycle state of a project."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SessionStatus(StrEnum):
    """Lifecycle state of a daily session."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class AssignmentStatus(StrEnum):
    """Response state snapshotted for a participant."""

    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    ABSENT = "ABSENT"
    NOT_ANSWERED = "NOT_ANSWERED"
    EXCUSED = "EXCUSED"


class NotificationKind(StrEnum):
    """Reminder stage sent for a daily session."""

    FIRST_REMINDER = "FIRST_REMINDER"
    LAST_REMINDER = "LAST_REMINDER"


class ReportKind(StrEnum):
    """Stable report period types."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class AuditAction(StrEnum):
    """Administrative and system actions retained in the audit history."""

    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_EDITED = "PROJECT_EDITED"
    PROJECT_ARCHIVED = "PROJECT_ARCHIVED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    MEMBER_LEFT_GUILD = "MEMBER_LEFT_GUILD"
    SCHEDULE_UPDATED = "SCHEDULE_UPDATED"
    QUESTION_ADDED = "QUESTION_ADDED"
    QUESTION_EDITED = "QUESTION_EDITED"
    QUESTION_MOVED = "QUESTION_MOVED"
    QUESTION_ACTIVATED = "QUESTION_ACTIVATED"
    QUESTION_DEACTIVATED = "QUESTION_DEACTIVATED"
    ADMIN_ROLE_ADDED = "ADMIN_ROLE_ADDED"
    ADMIN_ROLE_REMOVED = "ADMIN_ROLE_REMOVED"
    REPORT_CHANNEL_SAVED = "REPORT_CHANNEL_SAVED"
    REPORT_CHANNEL_REMOVED = "REPORT_CHANNEL_REMOVED"
    ABSENCE_JUSTIFIED = "ABSENCE_JUSTIFIED"
    DAILY_CLOSED_MANUALLY = "DAILY_CLOSED_MANUALLY"
    MANUAL_REPORT_REQUESTED = "MANUAL_REPORT_REQUESTED"
