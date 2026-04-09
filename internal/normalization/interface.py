"""Normalization interface."""

from typing import Protocol

from internal.pipeline.type import IngestedBatchBundle
from .type import MentionRecord, NormalizationBatch


class INormalizationUseCase(Protocol):
    def normalize(self, batch: IngestedBatchBundle) -> NormalizationBatch: ...


__all__ = ["INormalizationUseCase"]
