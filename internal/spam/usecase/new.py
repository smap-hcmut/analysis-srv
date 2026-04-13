"""Factory for SpamUseCase."""

from ..interface import ISpamUseCase
from .score_authors import SpamScoringService
from .usecase import SpamUseCase


def New(
    *,
    mention_threshold: float = 0.65,
    author_threshold: float = 0.65,
) -> ISpamUseCase:
    service = SpamScoringService(
        mention_threshold=mention_threshold,
        author_threshold=author_threshold,
    )
    return SpamUseCase(service=service)


__all__ = ["New"]
