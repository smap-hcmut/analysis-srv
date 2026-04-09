#!/usr/bin/env python3
"""scripts/replay_batch.py — CLI tool to replay a batch through the analysis pipeline.

Usage:
    uv run python scripts/replay_batch.py \\
        --project-id proj-123 \\
        --campaign-id camp-456 \\
        --input-file /path/to/records.json \\
        [--run-id custom-run-id] \\
        [--dry-run]

Input file format (JSON array of UAP records):
    [
        {"ingest": {"project_id": "proj-123"}, "content": {"doc_id": "d1", "text": "..."}, ...},
        ...
    ]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from loguru import logger


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Replay a batch of UAP records through the analysis pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--project-id", required=True, help="Project identifier")
    p.add_argument("--campaign-id", default="", help="Campaign identifier (optional)")
    p.add_argument(
        "--input-file",
        required=True,
        help="Path to JSON file with array of UAP record dicts",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="Override run ID (default: auto-generated UUID)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate input, then exit without running the pipeline",
    )
    return p


def _load_records(input_file: str) -> list[dict]:
    path = Path(input_file)
    if not path.exists():
        logger.error("Input file not found: {}", input_file)
        sys.exit(1)

    with path.open() as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.error(
            "Input file must contain a JSON array, got: {}", type(data).__name__
        )
        sys.exit(1)

    return data


def _dict_to_uap_record(d: dict):  # type: ignore[return]
    """Convert a plain dict to a UAPRecord (best-effort; missing fields get defaults)."""
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent

    ingest_data = d.get("ingest", {})
    content_data = d.get("content", {})

    ingest = UAPIngest(project_id=ingest_data.get("project_id", ""))
    content = UAPContent(
        doc_id=content_data.get("doc_id", str(uuid.uuid4())),
        text=content_data.get("text", ""),
    )
    return UAPRecord(ingest=ingest, content=content)


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    run_id = args.run_id or f"replay-{uuid.uuid4().hex[:12]}"

    logger.info(
        "replay_batch: starting | project={} campaign={} run_id={} dry_run={}",
        args.project_id,
        args.campaign_id,
        run_id,
        args.dry_run,
    )

    raw_records = _load_records(args.input_file)
    logger.info(
        "replay_batch: loaded {} records from {}", len(raw_records), args.input_file
    )

    if args.dry_run:
        logger.info("replay_batch: --dry-run flag set, skipping pipeline execution")
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "run_id": run_id,
                    "project_id": args.project_id,
                    "campaign_id": args.campaign_id,
                    "record_count": len(raw_records),
                },
                indent=2,
            )
        )
        return

    # Build pipeline inputs
    from internal.model.uap import UAPRecord
    from internal.pipeline.type import (
        IngestedBatchBundle,
        PipelineConfig,
        PipelineServices,
    )
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.normalization.usecase.new import New as new_normalization_usecase
    from internal.dedup.usecase.new import New as new_dedup_usecase
    from internal.spam.usecase.new import New as new_spam_usecase
    from internal.threads.usecase.new import New as new_threads_usecase
    from internal.enrichment.usecase.new import new_enrichment_usecase
    from internal.reporting.usecase.new import new_reporting_usecase
    from internal.crisis.usecase.new import new_crisis_usecase

    uap_records: list[UAPRecord] = [_dict_to_uap_record(d) for d in raw_records]

    batch = IngestedBatchBundle(
        records=uap_records,
        project_id=args.project_id,
        campaign_id=args.campaign_id,
    )
    ctx = RunContext(run_id=run_id, project_id=args.project_id)
    config = PipelineConfig(
        enable_normalization=True,
        enable_dedup=True,
        enable_spam=True,
        enable_threads=True,
        enable_enrichment=True,
        enable_reporting=True,
        enable_crisis=True,
        services=PipelineServices(
            normalization=new_normalization_usecase(),
            dedup=new_dedup_usecase(),
            spam=new_spam_usecase(),
            threads=new_threads_usecase(),
            enrichment=new_enrichment_usecase(),
            reporting=new_reporting_usecase(),
            crisis=new_crisis_usecase(),
        ),
    )

    logger.info("replay_batch: running pipeline...")
    result = run_pipeline(batch, ctx, config)

    crisis_level = (
        result.crisis_assessment.crisis_level
        if result.crisis_assessment is not None
        else "none"
    )

    summary = {
        "run_id": result.run_id,
        "project_id": args.project_id,
        "campaign_id": args.campaign_id,
        "total_valid_records": result.total_valid_records,
        "insight_card_count": len(result.insight_cards),
        "has_bi_bundle": result.bi_bundle is not None,
        "crisis_level": crisis_level,
        "stage_timings": result.stage_timings,
    }

    print(json.dumps(summary, indent=2))
    logger.info(
        "replay_batch: done | records={} crisis_level={}",
        result.total_valid_records,
        crisis_level,
    )


if __name__ == "__main__":
    main()
