"""Module-specific errors for analyzed_post domain."""


class ErrPostNotFound(Exception):
    """Raised when analyzed post is not found."""
    pass


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrDuplicatePost(Exception):
    """Raised when post already exists."""
    pass


__all__ = [
    "ErrPostNotFound",
    "ErrInvalidInput",
    "ErrDuplicatePost",
]
