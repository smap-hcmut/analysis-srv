from typing import Optional

from pkg.logger.logger import Logger
from internal.impact_calculation.interface import IImpactCalculationUseCase
from internal.impact_calculation.type import Config
from .usecase import ImpactCalculationUseCase


def New(config: Config, logger: Optional[Logger] = None) -> IImpactCalculationUseCase:
    return ImpactCalculationUseCase(config=config, logger=logger)
