"""Pipeline stage helpers — timing wrapper and stage runner."""

import time
from typing import Callable, Any

from ..type import PipelineFacts, StageResult, IngestedBatchBundle, PipelineConfig
from ..errors import StageError
from internal.runtime.type import RunContext


def _run_stage(
    stage_name: str,
    stage_fn: Callable[
        [PipelineFacts, IngestedBatchBundle, RunContext, PipelineConfig], PipelineFacts
    ],
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> tuple[PipelineFacts, StageResult]:
    """Execute one pipeline stage with timing. Returns updated facts + stage result."""
    records_in = len(batch.records)
    t0 = time.monotonic()
    try:
        updated_facts = stage_fn(facts, batch, ctx, config)
        elapsed = time.monotonic() - t0
        # Use normalized_records count as records_out when available (post-normalization
        # stages), otherwise fall back to the raw input batch size.
        records_out = (
            len(updated_facts.normalized_records)
            if updated_facts.normalized_records
            else records_in
        )
        return updated_facts, StageResult(
            stage_name=stage_name,
            elapsed_seconds=elapsed,
            records_in=records_in,
            records_out=records_out,
        )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        raise StageError(stage_name, exc) from exc


def _collect_timings(stage_results: list[StageResult]) -> dict[str, float]:
    """Build a {stage_name: elapsed_seconds} dict for the run manifest."""
    return {sr.stage_name: sr.elapsed_seconds for sr in stage_results}


__all__ = ["_run_stage", "_collect_timings"]
