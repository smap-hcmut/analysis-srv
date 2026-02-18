class ErrPostNotFound(Exception):
    pass


class ErrInvalidInput(Exception):
    pass


class ErrDuplicatePost(Exception):
    pass


__all__ = [
    "ErrPostNotFound",
    "ErrInvalidInput",
    "ErrDuplicatePost",
]
