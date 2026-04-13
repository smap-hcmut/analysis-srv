"""Dedup interface."""

from typing import Protocol

from internal.normalization.type import MentionRecord
from .type import DedupAnalysisResult


class IDeduplicationUseCase(Protocol):
    def annotate(
        self, mentions: list[MentionRecord]
    ) -> tuple[list[MentionRecord], DedupAnalysisResult]: ...


__all__ = ["IDeduplicationUseCase"]
