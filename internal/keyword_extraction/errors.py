"""Module-specific errors for keyword_extraction domain."""


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrExtractionFailed(Exception):
    """Raised when keyword extraction fails."""
    pass


class ErrDictionaryLoadFailed(Exception):
    """Raised when aspect dictionary loading fails."""
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrExtractionFailed",
    "ErrDictionaryLoadFailed",
]
