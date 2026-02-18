import json
from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from internal.model.insight_message import InsightMessage
from .type import PublishConfig
from .constant import TOPIC_ANALYTICS_OUTPUT, DEFAULT_BATCH_SIZE


class AnalyticsPublisher:
    def __init__(
        self,
        kafka_producer: IKafkaProducer,
        config: Optional[PublishConfig] = None,
        logger: Optional[Logger] = None,
    ):
        self._producer = kafka_producer
        self._config = config or PublishConfig(
            topic=TOPIC_ANALYTICS_OUTPUT,
            batch_size=DEFAULT_BATCH_SIZE,
        )
        self._logger = logger
        self._buffer: list[InsightMessage] = []

    async def publish(self, enriched: InsightMessage) -> None:
        if not self._config.enabled:
            return

        self._buffer.append(enriched)

        if len(self._buffer) >= self._config.batch_size:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return

        batch = self._buffer.copy()
        self._buffer.clear()

        try:
            # Serialize batch as JSON array
            payload = [item.to_dict() for item in batch]
            value_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            # Use project_id from first item as Kafka key (partition routing)
            key = batch[0].project.project_id if batch else ""
            key_bytes = key.encode("utf-8") if key else None

            await self._producer.send(
                topic=self._config.topic,
                value=value_bytes,
                key=key_bytes,
            )

            if self._logger:
                self._logger.info(
                    f"internal.analytics.delivery.kafka.producer.publisher: Published batch of {len(batch)} "
                    f"to topic={self._config.topic}, key={key}"
                )

        except Exception as exc:
            # Re-add to buffer for retry on next publish
            self._buffer = batch + self._buffer
            if self._logger:
                self._logger.error(
                    f"internal.analytics.delivery.kafka.producer.publisher: Failed to publish batch: {exc}"
                )
            raise

    async def close(self) -> None:
        if self._buffer:
            await self.flush()


__all__ = ["AnalyticsPublisher"]
