from typing import Optional

from pkg.logger.logger import Logger
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.intent_classification.type import Config
from .usecase import IntentClassificationUseCase


def New(
    config: Config, logger: Optional[Logger] = None
) -> IIntentClassificationUseCase:
    return IntentClassificationUseCase(config=config, logger=logger)
