from typing import Optional

from pkg.logger.logger import Logger
from ..interface import IPipelineUseCase
from .usecase import PipelineUseCase


def New(logger: Optional[Logger] = None) -> IPipelineUseCase:
    """Factory for PipelineUseCase."""
    return PipelineUseCase(logger=logger)


__all__ = ["New"]
