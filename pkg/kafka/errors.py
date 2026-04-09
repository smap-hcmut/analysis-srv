"""Kafka error types."""


class KafkaConsumerError(Exception):
    """Base exception for Kafka consumer operations."""

    pass


class KafkaProducerError(Exception):
    """Base exception for Kafka producer operations."""

    pass


__all__ = ["KafkaConsumerError", "KafkaProducerError"]
