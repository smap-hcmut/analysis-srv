from typing import Optional

from pkg.logger.logger import Logger
from internal.impact_calculation.type import Config
from .impact_calculation import ImpactCalculation


def New(config: Config, logger: Optional[Logger] = None) -> ImpactCalculation:
    """Create new ImpactCalculation instance.

    Args:
        config: Configuration for impact calculation
        logger: Logger instance (optional, for logging)

    Returns:
        ImpactCalculation instance

    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")

    return ImpactCalculation(config, logger)


__all__ = ["New"]
