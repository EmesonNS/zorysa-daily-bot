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
