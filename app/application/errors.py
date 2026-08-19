"""Expected application errors safe to expose in ephemeral interactions."""


class ApplicationError(RuntimeError):
    """Base error whose message is safe to show to a Discord user."""


class AuthorizationError(ApplicationError):
    """Raised when an actor cannot administer the current guild."""


class ConflictError(ApplicationError):
    """Raised when a requested state already exists or cannot be changed."""


class NotFoundError(ApplicationError):
    """Raised when a guild-scoped resource does not exist."""


class ValidationError(ApplicationError):
    """Raised when input does not satisfy an application invariant."""
