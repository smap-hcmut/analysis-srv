from typing import Optional

from pkg.logger.logger import Logger
from ..repository.interface import IPostInsightRepository
from ..interface import IPostInsightUseCase
from .usecase import PostInsightUseCase


def New(
    repository: IPostInsightRepository,
    logger: Optional[Logger] = None,
) -> IPostInsightUseCase:
    return PostInsightUseCase(repository=repository, logger=logger)


__all__ = ["New"]
