"""Threads interface."""

from typing import Protocol

from internal.normalization.type import MentionRecord
from .type import ThreadBundle


class IThreadsUseCase(Protocol):
    def build(self, mentions: list[MentionRecord]) -> ThreadBundle: ...


__all__ = ["IThreadsUseCase"]
