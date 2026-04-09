"""ThreadsUseCase — thin wrapper around build_threads."""

from internal.normalization.type import MentionRecord
from ..type import ThreadBundle
from ..interface import IThreadsUseCase
from .build_threads import build_threads


class ThreadsUseCase:
    """Satisfies IThreadsUseCase Protocol."""

    def build(self, mentions: list[MentionRecord]) -> ThreadBundle:
        return build_threads(mentions)


__all__ = ["ThreadsUseCase"]
