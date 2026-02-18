import asyncio
from typing import Optional

from pkg.kafka.consumer import KafkaConsumer
from pkg.kafka.type import KafkaMessage
from internal.analytics.delivery.kafka.consumer import new_kafka_handler

from .interface import IConsumerServer
from .type import Dependencies


class ConsumerServer(IConsumerServer):
    def __init__(self, deps: Dependencies):
        self.deps = deps
        self.logger = deps.logger
        self._running = False

        # Consumer management
        self.consumer: Optional[KafkaConsumer] = None
        self.handler = None
        self.consumer_task: Optional[asyncio.Task] = None

        # Domain services registry
        self.registry = None
        self.domain_services = None

    async def start(self) -> None:
        try:
            # Initialize domain services via registry
            from .registry import ConsumerRegistry

            self.registry = ConsumerRegistry(self.deps)
            self.domain_services = self.registry.initialize()

            # Get Kafka consumer config from dependencies
            kafka_consumer_config = self.deps.kafka_consumer_config
            if not kafka_consumer_config:
                raise ValueError(
                    "Kafka consumer configuration not provided in dependencies"
                )

            # Log subscription intent per topic (config-driven)
            for topic in kafka_consumer_config.topics:
                self.logger.info(
                    "Subscribing to topic=%s "
                    "(group_id=%s, auto_offset_reset=%s, "
                    "enable_auto_commit=%s, max_poll_records=%s, session_timeout_ms=%s)"
                    % (
                        topic,
                        kafka_consumer_config.group_id,
                        kafka_consumer_config.auto_offset_reset,
                        kafka_consumer_config.enable_auto_commit,
                        kafka_consumer_config.max_poll_records,
                        kafka_consumer_config.session_timeout_ms,
                    )
                )

            # Create Kafka consumer
            self.consumer = KafkaConsumer(kafka_consumer_config)
            await self.consumer.start()

            # Create analytics handler
            self.handler = new_kafka_handler(
                pipeline=self.domain_services.analytics_handler.pipeline,
                logger=self.logger,
            )

            self.logger.info("Kafka consumer started, waiting for messages...")

            # Start consuming
            self._running = True
            self.consumer_task = asyncio.create_task(
                self._consume_loop(), name="kafka-consumer"
            )

            # Wait for consumer task
            await self.consumer_task

        except asyncio.CancelledError:
            self.logger.info("Kafka consumer server cancelled")

        except Exception as e:
            self.logger.error(f"Failed to start Kafka consumer server: {e}")
            self.logger.exception("Server start error:")
            raise

    async def _consume_loop(self) -> None:
        try:

            async def message_handler(message: KafkaMessage) -> None:
                await self.handler.handle(message)

            # Start consuming (blocks until shutdown)
            await self.consumer.consume(message_handler)

        except asyncio.CancelledError:
            self.logger.info("Consume loop cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error in consume loop: {e}")
            self.logger.exception("Consume loop error:")
            raise

    async def shutdown(self) -> None:
        try:
            self.logger.info("Shutting down Kafka consumer server...")
            self._running = False

            # Cancel consumer task
            if self.consumer_task and not self.consumer_task.done():
                self.consumer_task.cancel()
                try:
                    await self.consumer_task
                except asyncio.CancelledError:
                    pass

            # Stop Kafka consumer
            if self.consumer:
                await self.consumer.stop()

            # Cleanup domain services
            if self.registry:
                self.registry.shutdown()

            self.logger.info("Kafka consumer server shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.logger.exception("Shutdown error:")

    def is_running(self) -> bool:
        return self._running


__all__ = ["ConsumerServer"]
