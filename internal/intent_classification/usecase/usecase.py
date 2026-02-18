from typing import Optional, Pattern as RePattern

from pkg.logger.logger import Logger
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.intent_classification.type import Config, Input, Output, Intent
from .helpers import compile_patterns
from .process import process as _process


class IntentClassificationUseCase(IIntentClassificationUseCase):
    def __init__(self, config: Config, logger: Optional[Logger] = None):
        self.config = config
        self.logger = logger

        self.patterns: dict[Intent, list[RePattern]] = compile_patterns(
            config, self.logger
        )

    def process(self, input_data: Input) -> Output:
        return _process(
            input_data=input_data,
            patterns=self.patterns,
            logger=self.logger,
        )
