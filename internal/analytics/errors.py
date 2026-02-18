"""Module-specific errors for analytics domain."""


class ErrPipelineProcessing(Exception):
    """Raised when pipeline processing fails."""

    pass


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""

    pass


class ErrPreprocessingFailed(Exception):
    """Raised when text preprocessing fails."""

    pass


class ErrPersistenceFailed(Exception):
    """Raised when saving analytics result fails."""

    pass


class ErrUAPValidation(Exception):
    """Raised when UAP message structure is invalid."""

    pass


class ErrUAPVersionUnsupported(Exception):
    """Raised when UAP version is not supported."""

    pass


__all__ = [
    "ErrPipelineProcessing",
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
    "ErrPersistenceFailed",
    "ErrUAPValidation",
    "ErrUAPVersionUnsupported",
]
