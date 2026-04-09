"""Factory for IngestionUseCase."""

from typing import Optional

from pkg.logger.logger import Logger
from .usecase import IngestionUseCase


def New(logger: Optional[Logger] = None) -> IngestionUseCase:
    return IngestionUseCase(logger=logger)


__all__ = ["New"]
