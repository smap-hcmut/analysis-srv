class ErrPipelineProcessing(Exception):
    pass


class ErrInvalidInput(Exception):
    pass


class ErrPreprocessingFailed(Exception):
    pass


class ErrPersistenceFailed(Exception):
    pass


__all__ = [
    "ErrPipelineProcessing",
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
    "ErrPersistenceFailed",
]
