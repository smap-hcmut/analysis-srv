from typing import Optional

from pkg.logger.logger import Logger
from ..type import IngestedBatchBundle, PipelineRunResult, PipelineConfig
from ..interface import IPipelineUseCase
from .run_pipeline import run_pipeline
from internal.runtime.type import RunContext


class PipelineUseCase:
    """Thin wrapper around run_pipeline() — satisfies IPipelineUseCase Protocol."""

    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger

    def run(
        self,
        batch: IngestedBatchBundle,
        ctx: RunContext,
        config: PipelineConfig,
    ) -> PipelineRunResult:
        if self.logger:
            self.logger.info(
                f"internal.pipeline.usecase: Starting run_id={ctx.run_id}, "
                f"records={len(batch.records)}, project_id={ctx.project_id}"
            )

        result = run_pipeline(batch, ctx, config)

        if self.logger:
            self.logger.info(
                f"internal.pipeline.usecase: Completed run_id={ctx.run_id}, "
                f"timings={result.stage_timings}"
            )

        return result


__all__ = ["PipelineUseCase"]
