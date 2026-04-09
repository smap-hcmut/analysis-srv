"""IngestionUseCase — thin orchestrator for the ingestion stage."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.model.uap import UAPRecord
from internal.pipeline.type import IngestedBatchBundle
from ..type import IngestionStats
from .kafka_adapter import adapt_kafka_records
from .ingest_batch import ingest_batch


class IngestionUseCase:
    def __init__(self, logger: Optional[Logger] = None) -> None:
        self.logger = logger

    def from_kafka(
        self,
        records: list[UAPRecord],
        *,
        project_id: str,
        campaign_id: str,
    ) -> tuple[IngestedBatchBundle, IngestionStats]:
        """Adapt raw Kafka records into a pipeline-ready bundle."""
        bundle, stats = adapt_kafka_records(
            records, project_id=project_id, campaign_id=campaign_id
        )
        if self.logger and stats.invalid_records:
            self.logger.warning(
                f"internal.ingestion: {stats.invalid_records} invalid records skipped "
                f"(project_id={project_id!r})"
            )
        return bundle, stats

    def validate(self, bundle: IngestedBatchBundle) -> IngestionStats:
        """Run validation pass on an existing bundle."""
        return ingest_batch(bundle)


__all__ = ["IngestionUseCase"]
