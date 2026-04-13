"""crisis/errors.py — crisis detection error types."""


class CrisisError(Exception):
    """Base error for crisis detection failures."""


__all__ = ["CrisisError"]
