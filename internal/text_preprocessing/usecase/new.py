from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.type import Config
from .text_processing import TextProcessing


def New(config: Config, logger: Optional[Logger] = None) -> TextProcessing:
    """Create new TextProcessing instance.

    Args:
        config: Configuration for text processing
        logger: Logger instance (optional, for logging)

    Returns:
        TextProcessing instance

    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")

    return TextProcessing(config, logger)


__all__ = ["New"]
