from typing import Optional

from pkg.logger.logger import Logger
from internal.intent_classification.type import Config
from .intent_classification import IntentClassification


def New(config: Config, logger: Optional[Logger] = None) -> IntentClassification:
    """Create new IntentClassification instance.

    Args:
        config: Configuration for intent classification
        logger: Logger instance (optional, for logging)

    Returns:
        IntentClassification instance

    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")

    return IntentClassification(config, logger)


__all__ = ["New"]
