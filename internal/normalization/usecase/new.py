"""Factory for NormalizationUseCase."""

from ..interface import INormalizationUseCase
from .usecase import NormalizationUseCase


def New() -> INormalizationUseCase:
    """Return a NormalizationUseCase instance."""
    return NormalizationUseCase()


__all__ = ["New"]
