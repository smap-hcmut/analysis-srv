"""Spam interface."""

from typing import Protocol

from internal.normalization.type import MentionRecord
from .type import QualityAnalysisResult


class ISpamUseCase(Protocol):
    def annotate(
        self, mentions: list[MentionRecord]
    ) -> tuple[list[MentionRecord], QualityAnalysisResult]: ...


__all__ = ["ISpamUseCase"]
