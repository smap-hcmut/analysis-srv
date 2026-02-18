from typing import Optional

from pkg.logger.logger import Logger
from internal.impact_calculation.interface import IImpactCalculationUseCase
from internal.impact_calculation.type import Input, Output, Config
from .process import process as _process


class ImpactCalculationUseCase(IImpactCalculationUseCase):
    def __init__(self, config: Config, logger: Optional[Logger] = None):
        self.config = config
        self.logger = logger

    def process(self, input_data: Input) -> Output:
        return _process(
            input_data=input_data,
            config=self.config,
            logger=self.logger,
        )
