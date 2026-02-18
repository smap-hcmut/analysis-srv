class ErrInvalidInput(Exception):
    pass


class ErrPreprocessingFailed(Exception):
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
]
