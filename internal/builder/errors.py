class ErrBuildFailed(Exception):
    pass


class ErrMissingUAPRecord(Exception):
    pass


__all__ = [
    "ErrBuildFailed",
    "ErrMissingUAPRecord",
]
