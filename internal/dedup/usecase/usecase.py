"""DeduplicationUseCase — thin wrapper around DeduplicationService."""

from internal.normalization.type import MentionRecord
from ..type import DedupAnalysisResult
from ..interface import IDeduplicationUseCase
from .annotate_dedup import DeduplicationService


class DeduplicationUseCase:
    """Satisfies IDeduplicationUseCase Protocol."""

    def __init__(self, service: DeduplicationService) -> None:
        self._service = service

    def annotate(
        self, mentions: list[MentionRecord]
    ) -> tuple[list[MentionRecord], DedupAnalysisResult]:
        return self._service.annotate(mentions)


__all__ = ["DeduplicationUseCase"]
