class ErrInvalidInput(Exception):
    pass


class ErrPatternLoadFailed(Exception):
    pass


class ErrClassificationFailed(Exception):
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrPatternLoadFailed",
    "ErrClassificationFailed",
]
