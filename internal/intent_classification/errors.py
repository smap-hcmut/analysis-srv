"""Module-specific errors for intent_classification domain."""


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrPatternLoadFailed(Exception):
    """Raised when pattern loading fails."""
    pass


class ErrClassificationFailed(Exception):
    """Raised when classification fails."""
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrPatternLoadFailed",
    "ErrClassificationFailed",
]
