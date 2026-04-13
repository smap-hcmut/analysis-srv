"""Threads module — groups mentions into thread bundles with lineage context."""

from .type import ThreadEdge, MentionContext, ThreadSummary, ThreadBundle
from .interface import IThreadsUseCase

__all__ = [
    "ThreadEdge",
    "MentionContext",
    "ThreadSummary",
    "ThreadBundle",
    "IThreadsUseCase",
]
