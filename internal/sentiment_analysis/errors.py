class ErrInvalidInput(Exception):
    pass


class ErrAnalysisFailed(Exception):
    pass


class ErrModelNotLoaded(Exception):
    pass


__all__ = [
    "ErrInvalidInput",
    "ErrAnalysisFailed",
    "ErrModelNotLoaded",
]
