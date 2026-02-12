"""Factory function for creating analyzed post use case."""

from typing import Optional

from pkg.logger.logger import Logger
from ..repository.interface import IAnalyzedPostRepository
from .usecase import AnalyzedPostUseCase


def New(
    repository: IAnalyzedPostRepository,
    logger: Optional[Logger] = None,
) -> AnalyzedPostUseCase:
    """Create a new analyzed post use case instance.
    
    Args:
        repository: Repository for data access
        logger: Logger instance (optional)
        
    Returns:
        AnalyzedPostUseCase instance
    """
    return AnalyzedPostUseCase(repository=repository, logger=logger)


__all__ = ["New"]
