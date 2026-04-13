"""Ingestion interface — Protocol for all ingestion adapters."""

from typing import Protocol

from internal.model.uap import UAPRecord
from .type import IngestedBatchBundle, IngestionStats


class IIngestionAdapter(Protocol):
    """Converts raw records into an `IngestedBatchBundle`."""

    def adapt(
        self,
        records: list[UAPRecord],
        *,
        project_id: str,
        campaign_id: str,
    ) -> tuple[IngestedBatchBundle, IngestionStats]: ...


__all__ = ["IIngestionAdapter"]
