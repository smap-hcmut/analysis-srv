from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from .publisher import AnalyticsPublisher
from .type import PublishConfig


def New(
    kafka_producer: IKafkaProducer,
    config: Optional[PublishConfig] = None,
    logger: Optional[Logger] = None,
) -> AnalyticsPublisher:
    return AnalyticsPublisher(
        kafka_producer=kafka_producer,
        config=config,
        logger=logger,
    )


__all__ = ["New"]
