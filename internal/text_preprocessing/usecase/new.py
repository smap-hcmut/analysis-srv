from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.text_preprocessing.type import Config
from .usecase import TextPreprocessingUseCase


def New(
    config: Config,
    logger: Optional[Logger] = None,
) -> ITextPreprocessingUseCase:
    return TextPreprocessingUseCase(config=config, logger=logger)


__all__ = ["New"]
