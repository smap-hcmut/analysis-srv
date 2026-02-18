class ErrInvalidInput(Exception):
    pass


class ErrCalculationFailed(Exception):
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrCalculationFailed",
]
