"""outbox/errors.py — outbox error types."""


class OutboxError(Exception):
    """Base outbox error."""


class OutboxWriteError(OutboxError):
    """Raised when an outbox record cannot be written to the DB."""


class OutboxRelayError(OutboxError):
    """Raised when the relay loop encounters an unrecoverable error."""


__all__ = ["OutboxError", "OutboxWriteError", "OutboxRelayError"]
