"""Kafka consumer for analytics service."""

from .handler import AnalyticsKafkaHandler
from .new import new_kafka_handler

__all__ = [
    "AnalyticsKafkaHandler",
    "new_kafka_handler",
]
