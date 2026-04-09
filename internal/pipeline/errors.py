class PipelineError(Exception):
    """Base error for pipeline orchestration failures."""


class StageTimeoutError(PipelineError):
    """Raised when a pipeline stage exceeds its time budget."""

    def __init__(self, stage: str, elapsed: float, limit: float):
        super().__init__(
            f"Stage '{stage}' timed out: {elapsed:.2f}s > limit {limit:.2f}s"
        )
        self.stage = stage
        self.elapsed = elapsed
        self.limit = limit


class StageError(PipelineError):
    """Raised when a pipeline stage fails with an unrecoverable error."""

    def __init__(self, stage: str, cause: Exception):
        super().__init__(f"Stage '{stage}' failed: {cause}")
        self.stage = stage
        self.cause = cause


__all__ = ["PipelineError", "StageTimeoutError", "StageError"]
