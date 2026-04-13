"""NormalizationUseCase — wraps normalize_mentions()."""

from internal.pipeline.type import IngestedBatchBundle
from ..type import NormalizationBatch
from ..interface import INormalizationUseCase
from .normalize_mentions import normalize_mentions


class NormalizationUseCase:
    """Satisfies INormalizationUseCase Protocol."""

    def normalize(self, batch: IngestedBatchBundle) -> NormalizationBatch:
        return normalize_mentions(batch)


__all__ = ["NormalizationUseCase"]
