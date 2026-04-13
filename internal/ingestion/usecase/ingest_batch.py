"""ingest_batch.py — validate an IngestedBatchBundle before it enters the pipeline."""

from internal.pipeline.type import IngestedBatchBundle
from ..type import IngestionStats
from ..errors import InvalidRecordError


def ingest_batch(bundle: IngestedBatchBundle) -> IngestionStats:
    """Validate records in the bundle and return aggregated stats.

    Raises InvalidRecordError on the first hard-failure record.
    Soft errors (missing optional fields) are recorded in stats only.
    """
    stats = IngestionStats(total_records=len(bundle.records))

    for rec in bundle.records:
        doc_id = rec.content.doc_id or rec.event_id or "<unknown>"
        if not rec.content.doc_id:
            raise InvalidRecordError(doc_id, "content.doc_id is required")
        if not rec.ingest.project_id:
            raise InvalidRecordError(doc_id, "ingest.project_id is required")
        stats.valid_records += 1

    return stats


__all__ = ["ingest_batch"]
