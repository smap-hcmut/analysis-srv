import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from pkg.kafka.consumer import KafkaConsumer
from pkg.kafka.type import KafkaMessage
from internal.model.uap import UAPRecord, ErrUAPValidation, ErrUAPVersionUnsupported
from internal.runtime.type import RunContext
from internal.analytics.usecase.batch_enricher import NLPBatchEnricher

# UAP version header field (replaces internal.analytics.delivery.constant import)
FIELD_UAP_VERSION = "uap_version"

from .interface import IConsumerServer
from .type import Dependencies


class ConsumerServer(IConsumerServer):
    def __init__(self, deps: Dependencies):
        self.deps = deps
        self.logger = deps.logger
        self._running = False

        # Consumer management
        self.consumer: Optional[KafkaConsumer] = None
        self.consumer_task: Optional[asyncio.Task] = None

        # Domain services registry
        self.registry = None
        self.domain_services = None

        # Pipeline references (wired after registry.initialize())
        self.pipeline_usecase = None
        self.pipeline_config = None
        self.ingestion_usecase = None
        self.contract_publisher = None
        self.post_insight_usecase = None

    async def start(self) -> None:
        try:
            from .registry import ConsumerRegistry

            self.registry = ConsumerRegistry(self.deps)
            self.domain_services = self.registry.initialize()

            # Grab pipeline references from registry
            self.pipeline_usecase = self.registry.pipeline_usecase
            self.pipeline_config = self.registry.pipeline_config
            self.ingestion_usecase = self.registry.ingestion_usecase
            self.contract_publisher = self.registry.contract_publisher
            self.post_insight_usecase = self.registry.post_insight_usecase

            # Get Kafka consumer config from dependencies
            kafka_consumer_config = self.deps.kafka_consumer_config
            if not kafka_consumer_config:
                raise ValueError(
                    "Kafka consumer configuration not provided in dependencies"
                )

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

            self.consumer = KafkaConsumer(kafka_consumer_config)
            await self.consumer.start()

            self.logger.info("Kafka consumer started, waiting for messages...")

            self._running = True
            self.consumer_task = asyncio.create_task(
                self._consume_loop(), name="kafka-consumer"
            )
            await self.consumer_task

        except asyncio.CancelledError:
            self.logger.info("Kafka consumer server cancelled")

        except Exception as e:
            self.logger.error(f"Failed to start Kafka consumer server: {e}")
            self.logger.exception("Server start error:")
            raise

    async def _handle_message(self, message: KafkaMessage) -> None:
        """Process a single Kafka message through the full pipeline.

        Flow:
            Kafka message
            → parse UAP
            → ingest → IngestedBatchBundle
            → asyncio.to_thread(pipeline.run)
                - normalization → dedup → spam → threads
                - NLP enrichment (preprocessing, intent, keyword, sentiment, impact)
            → async: persist each NLPFact to post_insight
            → async: publish each NLPFact to contract topics via ContractPublisher

        Errors are logged but never propagate to prevent disrupting offset commits.
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

            # 2. Format auto-detection: ingest-srv flat vs legacy UAP hierarchical
            if FIELD_UAP_VERSION in envelope:
                uap_record = UAPRecord.parse(envelope)  # legacy UAP format
            elif "identity" in envelope:
                uap_record = UAPRecord.from_ingest_record(
                    envelope
                )  # ingest-srv flat format
            else:
                return  # unknown format — skip silently

            project_id = uap_record.ingest.project_id if uap_record.ingest else None
            if not project_id:
                return

            # 3. Domain routing — resolve ontology overlay from domain_type_code
            domain_config = self.registry.domain_registry.lookup(
                uap_record.domain_type_code
            )
            uap_record.raw["_resolved_domain_overlay"] = (
                domain_config.contract_domain_overlay
            )

            # 4. Adapt to pipeline-ready bundle
            bundle, stats = self.ingestion_usecase.from_kafka(
                [uap_record],
                project_id=project_id,
                campaign_id="",
            )
            if not bundle.records:
                return

            # 5. Build run context with per-domain ontology overlay
            ctx = RunContext(
                run_id=str(uuid.uuid4()),
                project_id=project_id,
                analysis_window_end=datetime.now(tz=timezone.utc),
                ontology=domain_config.to_runtime_ontology(),
            )

            # 6. Run pipeline stages (CPU-bound; offload to thread pool)
            #    Includes: normalization → dedup → spam → threads → NLP enrichment
            result = await asyncio.to_thread(
                self.pipeline_usecase.run,
                bundle,
                ctx,
                self.pipeline_config,
            )

            self.logger.debug(
                f"internal.consumer.server: pipeline run_id={result.run_id}, "
                f"records={result.total_valid_records}, "
                f"nlp_facts={len(result.nlp_facts)}, "
                f"timings={result.stage_timings}"
            )

            # 7. Async: persist NLP facts to post_insight + publish to contract topics
            if result.nlp_facts:
                await self._persist_and_publish(result.nlp_facts)

        except (ErrUAPValidation, ErrUAPVersionUnsupported) as exc:
            self.logger.warning(f"internal.consumer.server: UAP error (skipped): {exc}")
        except json.JSONDecodeError as exc:
            self.logger.warning(f"internal.consumer.server: bad JSON (skipped): {exc}")
        except ValueError as exc:
            self.logger.warning(
                f"internal.consumer.server: validation error (skipped): {exc}"
            )
        except Exception as exc:
            self.logger.error(f"internal.consumer.server: unexpected error: {exc}")

    async def _persist_and_publish(self, nlp_facts: list) -> None:
        """Persist each NLPFact to post_insight and publish to contract topics.

        Non-fatal — errors are logged per-record; a single failure does not
        prevent the remaining facts from being persisted/published.
        """
        for nlp_fact in nlp_facts:
            # Persist to post_insight
            if self.post_insight_usecase and nlp_fact.analytics_result is not None:
                try:
                    pi_input = NLPBatchEnricher.to_post_insight_input(nlp_fact)
                    await self.post_insight_usecase.create(pi_input)
                except Exception as exc:
                    self.logger.error(
                        f"internal.consumer.server: post_insight persist failed: {exc}"
                    )

            # Publish to contract topics (auto-flushes at batch_size)
            if self.contract_publisher and nlp_fact.insight_message is not None:
                try:
                    await self.contract_publisher.publish_one(
                        uap=nlp_fact.uap_record,
                        msg=nlp_fact.insight_message,
                    )
                except Exception as exc:
                    self.logger.error(
                        f"internal.consumer.server: contract publish failed: {exc}"
                    )

    async def _consume_loop(self) -> None:
        try:

            async def message_handler(message: KafkaMessage) -> None:
                await self._handle_message(message)

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

            if self.consumer_task and not self.consumer_task.done():
                self.consumer_task.cancel()
                try:
                    await self.consumer_task
                except asyncio.CancelledError:
                    pass

            if self.consumer:
                await self.consumer.stop()

            if self.registry:
                self.registry.shutdown()

            self.logger.info("Kafka consumer server shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.logger.exception("Shutdown error:")

    def is_running(self) -> bool:
        return self._running


__all__ = ["ConsumerServer"]
