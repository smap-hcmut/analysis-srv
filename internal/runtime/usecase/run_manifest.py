"""run_manifest.py — build a lightweight run manifest for logging / audit.

Simplified port of core-analysis/src/smap/run_manifest.py#build_run_manifest.
Does NOT depend on pydantic, file I/O, or DuckDB.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from internal.runtime.type import RunContext
    from internal.pipeline.type import PipelineRunResult, PipelineConfig


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_run_manifest(
    ctx: "RunContext",
    result: "PipelineRunResult",
    config: "PipelineConfig",
) -> dict[str, Any]:
    """Build a structured audit manifest for a completed pipeline run.

    Returns a plain dict — caller can log it as JSON or store elsewhere.
    """
    return {
        "manifest_version": "2026.04.09-analysis-srv-r1",
        "run_id": ctx.run_id,
        "project_id": ctx.project_id,
        "generated_at": _utc_now_iso(),
        "analysis_window": {
            "start": ctx.analysis_window_start.isoformat()
            if ctx.analysis_window_start
            else None,
            "end": ctx.analysis_window_end.isoformat()
            if ctx.analysis_window_end
            else None,
        },
        "total_records": result.total_valid_records,
        "nlp_input_records": result.nlp_input_records,
        "nlp_output_records": len(result.nlp_facts),
        "filtered_out_unsupported_language": result.filtered_out_unsupported_language,
        "stage_timings": result.stage_timings,
        "pipeline_config": {
            "enable_normalization": config.enable_normalization,
            "enable_dedup": config.enable_dedup,
            "enable_spam": config.enable_spam,
            "enable_threads": config.enable_threads,
            "enable_enrichment": config.enable_enrichment,
            "enable_reporting": config.enable_reporting,
            "enable_crisis": config.enable_crisis,
        },
        "insight_card_count": len(result.insight_cards),
        "has_bi_bundle": result.bi_bundle is not None,
        "crisis_level": (
            result.crisis_assessment.crisis_level
            if result.crisis_assessment is not None
            else "none"
        ),
    }


__all__ = ["build_run_manifest"]
