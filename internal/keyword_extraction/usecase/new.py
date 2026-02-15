from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.type import Config
from .keyword_extraction import KeywordExtraction


def New(
    config: Config, ai_extractor: SpacyYake, logger: Optional[Logger] = None
) -> KeywordExtraction:
    """Create new KeywordExtraction instance.

    Args:
        config: Configuration for keyword extraction
        ai_extractor: SpacyYake instance for AI-powered extraction
        logger: Logger instance (optional, for logging)

    Returns:
        KeywordExtraction instance

    Raises:
        ValueError: If config or ai_extractor is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")

    if not isinstance(ai_extractor, SpacyYake):
        raise ValueError("ai_extractor must be an instance of SpacyYake")

    return KeywordExtraction(config, ai_extractor, logger)


__all__ = ["New"]
