"""Module-specific errors for text_preprocessing domain."""


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrPreprocessingFailed(Exception):
    """Raised when text preprocessing fails."""
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
]
