"""Factory function for creating analytics handler."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.analytics.interface import IAnalyticsPipeline
from .handler import AnalyticsHandler


def New(
    pipeline: IAnalyticsPipeline,
    logger: Optional[Logger] = None,
) -> AnalyticsHandler:
    """Create a new analytics handler instance.
    
    Args:
        pipeline: Analytics pipeline instance
        logger: Logger instance (optional)
        
    Returns:
        AnalyticsHandler instance
        
    Raises:
        ValueError: If pipeline is invalid
    """
    if pipeline is None:
        raise ValueError("pipeline cannot be None")
    
    return AnalyticsHandler(pipeline=pipeline, logger=logger)


__all__ = ["New"]
