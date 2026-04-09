"""Factory for DeduplicationUseCase."""

from ..interface import IDeduplicationUseCase
from .annotate_dedup import DeduplicationService
from .usecase import DeduplicationUseCase


def New(
    *,
    exact_enabled: bool = True,
    near_enabled: bool = True,
    near_similarity_threshold: float = 0.82,
) -> IDeduplicationUseCase:
    service = DeduplicationService(
        exact_enabled=exact_enabled,
        near_enabled=near_enabled,
        near_similarity_threshold=near_similarity_threshold,
    )
    return DeduplicationUseCase(service=service)


__all__ = ["New"]
