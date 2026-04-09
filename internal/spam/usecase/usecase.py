"""SpamUseCase — thin wrapper around SpamScoringService."""

from internal.normalization.type import MentionRecord
from ..type import QualityAnalysisResult
from ..interface import ISpamUseCase
from .score_authors import SpamScoringService


class SpamUseCase:
    """Satisfies ISpamUseCase Protocol."""

    def __init__(self, service: SpamScoringService) -> None:
        self._service = service

    def annotate(
        self, mentions: list[MentionRecord]
    ) -> tuple[list[MentionRecord], QualityAnalysisResult]:
        return self._service.annotate(mentions)


__all__ = ["SpamUseCase"]
