import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from pkg.kafka.consumer import KafkaConsumer
from pkg.kafka.type import KafkaMessage
from internal.analytics.delivery.kafka.consumer import new_kafka_handler
from internal.analytics.delivery.constant import FIELD_UAP_VERSION
from internal.model.uap import UAPRecord, ErrUAPValidation, ErrUAPVersionUnsupported
from internal.runtime.type import RunContext

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

        # Phase 3 pipeline (wired after registry.initialize())
        self.pipeline_usecase = None
        self.pipeline_config = None
        self.ingestion_usecase = None

    async def start(self) -> None:
        try:
            # Initialize domain services via registry
            from .registry import ConsumerRegistry

            self.registry = ConsumerRegistry(self.deps)
            self.domain_services = self.registry.initialize()

            # Grab Phase 3 pipeline references from the registry
            self.pipeline_usecase = self.registry.pipeline_usecase
            self.pipeline_config = self.registry.pipeline_config
            self.ingestion_usecase = self.registry.ingestion_usecase

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

    async def _handle_pipeline(self, message: KafkaMessage) -> None:
        """Run the Phase 3 pipeline (normalization → dedup → spam → threads) for one message.

        Runs in parallel with the legacy analytics handler; errors are logged but
        never propagate to prevent disrupting offset commits.
        """
        if self.pipeline_usecase is None or self.ingestion_usecase is None:
            return

        try:
            # 1. Decode message
            if isinstance(message.value, bytes):
                body = message.value.decode("utf-8")
            elif isinstance(message.value, str):
                body = message.value
            else:
                body = json.dumps(message.value)

            envelope = json.loads(body)

            # 2. Skip legacy messages without UAP version header
            if FIELD_UAP_VERSION not in envelope:
                return

            # 3. Parse UAP
            uap_record = UAPRecord.parse(envelope)
            project_id = uap_record.ingest.project_id if uap_record.ingest else None
            if not project_id:
                return

            # 4. Adapt to pipeline-ready bundle
            bundle, stats = self.ingestion_usecase.from_kafka(
                [uap_record],
                project_id=project_id,
                campaign_id="",
            )
            if not bundle.records:
                return

            # 5. Build run context
            ctx = RunContext(
                run_id=str(uuid.uuid4()),
                project_id=project_id,
                analysis_window_end=datetime.now(tz=timezone.utc),
            )

            # 6. Run pipeline stages (CPU-bound; offload to thread pool)
            result = await asyncio.to_thread(
                self.pipeline_usecase.run,
                bundle,
                ctx,
                self.pipeline_config,
            )

            if self.logger:
                self.logger.debug(
                    f"internal.consumer.server: pipeline run_id={result.run_id}, "
                    f"records={result.total_valid_records}, "
                    f"timings={result.stage_timings}"
                )

        except (ErrUAPValidation, ErrUAPVersionUnsupported) as exc:
            if self.logger:
                self.logger.warning(
                    f"internal.consumer.server: pipeline UAP error (skipped): {exc}"
                )
        except json.JSONDecodeError as exc:
            if self.logger:
                self.logger.warning(
                    f"internal.consumer.server: pipeline bad JSON (skipped): {exc}"
                )
        except ValueError as exc:
            if self.logger:
                self.logger.warning(
                    f"internal.consumer.server: pipeline validation error (skipped): {exc}"
                )
        except Exception as exc:
            # Non-fatal — log and continue; offset is still committed by legacy handler
            if self.logger:
                self.logger.error(
                    f"internal.consumer.server: pipeline unexpected error: {exc}"
                )

    async def _consume_loop(self) -> None:
        try:

            async def message_handler(message: KafkaMessage) -> None:
                # 1. Legacy analytics pipeline (NLP enrichment, contract publishing)
                await self.handler.handle(message)
                # 2. Phase 3 core-analysis pipeline (normalization, dedup, spam, threads)
                await self._handle_pipeline(message)

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
