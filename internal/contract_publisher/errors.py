class ContractPublishError(Exception):
    """Base error for contract publisher failures."""


class InvalidPayloadError(ContractPublishError):
    """Raised when a payload cannot be built due to missing required fields."""


class KafkaPublishError(ContractPublishError):
    """Raised when Kafka send fails for a contract topic."""

    def __init__(self, topic: str, cause: Exception):
        super().__init__(f"failed to publish to topic={topic}: {cause}")
        self.topic = topic
        self.cause = cause


__all__ = [
    "ContractPublishError",
    "InvalidPayloadError",
    "KafkaPublishError",
]
