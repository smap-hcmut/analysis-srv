from typing import Optional

from pkg.logger.logger import Logger
from internal.analytics.interface import IAnalyticsUseCase
from .handler import AnalyticsKafkaHandler


def new_kafka_handler(
    pipeline: IAnalyticsUseCase,
    logger: Optional[Logger] = None,
) -> AnalyticsKafkaHandler:
    return AnalyticsKafkaHandler(
        pipeline=pipeline,
        logger=logger,
    )


__all__ = ["new_kafka_handler"]
