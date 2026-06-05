"""kafka_adapter.py — converts UAPRecord[] (Kafka consumer) → IngestedBatchBundle."""

from internal.model.uap import UAPRecord
from internal.pipeline.type import IngestedBatchBundle
from ..type import IngestionStats


def adapt_kafka_records(
    records: list[UAPRecord],
    *,
    project_id: str,
    campaign_id: str,
) -> tuple[IngestedBatchBundle, IngestionStats]:
    """Convert UAPRecord[] (Kafka format) → IngestedBatchBundle.

    This is the single integration point between the old Kafka consumer and the
    new pipeline.  All records are kept as UAPRecord; the depth/root metadata
    is precomputed into a lookup that downstream stages can use.

    Returns:
        (IngestedBatchBundle, IngestionStats)
    """
    valid: list[UAPRecord] = []
    stats = IngestionStats(total_records=len(records))

    for rec in records:
        doc_id = rec.content.doc_id
        if not doc_id:
            stats.invalid_records += 1
            stats.error_messages.append(
                f"record missing doc_id (event_id={rec.event_id!r})"
            )
            continue
        if not rec.ingest.project_id:
            stats.invalid_records += 1
            stats.error_messages.append(f"record '{doc_id}' missing ingest.project_id")
            continue
        valid.append(rec)
        stats.valid_records += 1

    bundle = IngestedBatchBundle(
        records=valid,
        project_id=project_id,
        campaign_id=campaign_id,
    )
    return bundle, stats


__all__ = ["adapt_kafka_records"]
