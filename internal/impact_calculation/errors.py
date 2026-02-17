"""Module-specific errors for impact_calculation domain."""


class ErrInvalidInput(Exception):
    """Raised when input data is invalid."""
    pass


class ErrCalculationFailed(Exception):
    """Raised when impact calculation fails."""
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrCalculationFailed",
]
