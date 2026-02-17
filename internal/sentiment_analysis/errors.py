"""Module-specific errors for sentiment_analysis domain."""


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrAnalysisFailed(Exception):
    """Raised when sentiment analysis fails."""
    pass


class ErrModelNotLoaded(Exception):
    """Raised when PhoBERT model is not loaded."""
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrAnalysisFailed",
    "ErrModelNotLoaded",
]
