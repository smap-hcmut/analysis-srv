from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.keyword_extraction.type import Config
from .usecase import KeywordExtractionUseCase


def New(
    config: Config,
    ai_extractor: SpacyYake,
    logger: Optional[Logger] = None,
) -> IKeywordExtractionUseCase:
    return KeywordExtractionUseCase(config, ai_extractor, logger)
