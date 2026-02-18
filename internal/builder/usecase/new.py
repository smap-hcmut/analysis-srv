from typing import Optional

from pkg.logger.logger import Logger
from ..interface import IResultBuilderUseCase
from .usecase import ResultBuilderUseCase


def New(
    logger: Optional[Logger] = None,
) -> IResultBuilderUseCase:
    return ResultBuilderUseCase(logger=logger)


__all__ = ["New"]
