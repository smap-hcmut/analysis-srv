from typing import Protocol, runtime_checkable

from .type import IngestedBatchBundle, PipelineRunResult, PipelineConfig
from internal.runtime.type import RunContext


@runtime_checkable
class IPipelineUseCase(Protocol):
    """Orchestrates a full pipeline run over a batch of UAP records."""

    def run(
        self,
        batch: IngestedBatchBundle,
        ctx: RunContext,
        config: PipelineConfig,
    ) -> PipelineRunResult: ...


__all__ = ["IPipelineUseCase"]
