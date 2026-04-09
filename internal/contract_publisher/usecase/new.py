from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from internal.contract_publisher.type import ContractPublishConfig
from internal.contract_publisher.constant import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_FLUSH_INTERVAL_SECONDS,
)
from .usecase import ContractPublisherUseCase


def New(
    kafka_producer: IKafkaProducer,
    config: Optional[ContractPublishConfig] = None,
    logger: Optional[Logger] = None,
) -> ContractPublisherUseCase:
    """Factory for ContractPublisherUseCase.

    Usage:
        publisher = contract_publisher.usecase.new.New(
            kafka_producer=kafka_producer,
            config=ContractPublishConfig(
                batch_size=100,
                domain_overlay="domain-facial-cleanser-vn",
            ),
            logger=logger,
        )
    """
    if config is None:
        config = ContractPublishConfig(
            batch_size=DEFAULT_BATCH_SIZE,
            flush_interval_seconds=DEFAULT_FLUSH_INTERVAL_SECONDS,
        )

    return ContractPublisherUseCase(
        kafka_producer=kafka_producer,
        config=config,
        logger=logger,
    )


__all__ = ["New"]
