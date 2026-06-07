from typing import Optional

from pkg.logger.logger import Logger
from ..type import IngestedBatchBundle, PipelineRunResult, PipelineConfig
from .run_pipeline import run_pipeline
from internal.runtime.type import RunContext
from internal.observability.metrics import pipeline_runs_total, stage_duration_seconds


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

        # --- Prometheus instrumentation ---
        status = "error" if any(sr.error for sr in (result.stage_results or [])) else "ok"
        pipeline_runs_total.labels(status=status).inc()
        for stage_name, duration_s in (result.stage_timings or {}).items():
            stage_duration_seconds.labels(stage=stage_name).observe(duration_s)

        return result


__all__ = ["PipelineUseCase"]
