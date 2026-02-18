class ErrInvalidInput(Exception):
    pass


class ErrExtractionFailed(Exception):
    pass


class ErrDictionaryLoadFailed(Exception):
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrExtractionFailed",
    "ErrDictionaryLoadFailed",
]
