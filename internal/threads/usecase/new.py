"""Factory for ThreadsUseCase."""

from ..interface import IThreadsUseCase
from .usecase import ThreadsUseCase


def New() -> IThreadsUseCase:
    return ThreadsUseCase()


__all__ = ["New"]
