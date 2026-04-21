import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from pkg.kafka.consumer import KafkaConsumer
from pkg.kafka.type import KafkaMessage
from internal.model.uap import UAPRecord, ErrUAPValidation, ErrUAPVersionUnsupported
from internal.runtime.type import RunContext
from internal.analytics.usecase.batch_enricher import NLPBatchEnricher
from pkg.logger.logger import set_trace_id, set_project_id, clear_project_id

# UAP version header field (replaces internal.analytics.delivery.constant import)
FIELD_UAP_VERSION = "uap_version"

from .interface import IConsumerServer
from .type import Dependencies


class ConsumerServer(IConsumerServer):
    # Written once the Kafka consumer is running; deleted on shutdown.
    # startupProbe and livenessProbe check for this file so Kubernetes only
    # considers the pod ready when it is actually consuming messages.
    HEALTHZ_FILE = Path("/tmp/healthy")

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

            # Publish domain registry to Redis for cross-service discovery
            await self._publish_domain_registry()

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
            # Signal to Kubernetes probes that the consumer is fully up.
            self.HEALTHZ_FILE.write_text("ok")

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

    # ------------------------------------------------------------------
    # Redis domain registry publication
    # ------------------------------------------------------------------

    REDIS_KEY_DOMAINS = "smap:domains"

    async def _publish_domain_registry(self) -> None:
        """Publish the loaded domain list to Redis for cross-service discovery.

        Called once at startup after DomainLoader builds the DomainRegistry.
        Other services (e.g. project-srv) read this key to validate
        domain_type_code and to list available domains.

        Key: ``smap:domains`` (no TTL — overwritten on every restart).
        """
        domain_registry = self.registry.domain_registry
        if domain_registry is None:
            self.logger.warning("Domain registry is None, skipping Redis publish")
            return

        domains = []
        for code in domain_registry.domain_codes():
            cfg = domain_registry.lookup(code)
            domains.append(
                {
                    "domain_code": cfg.domain_code,
                    "display_name": cfg.display_name,
                }
            )

        ok = await self.deps.redis.set(self.REDIS_KEY_DOMAINS, domains)
        if ok:
            self.logger.info(
                "Published domain registry to Redis",
                extra={
                    "key": self.REDIS_KEY_DOMAINS,
                    "domain_count": len(domains),
                    "domains": [d["domain_code"] for d in domains],
                },
            )
        else:
            self.logger.error(
                "Failed to publish domain registry to Redis",
                extra={"key": self.REDIS_KEY_DOMAINS},
            )

    async def _parse_message(self, message: KafkaMessage) -> Optional[UAPRecord]:
        """Decode and parse a single Kafka message into a UAPRecord.

        Returns None (with a warning log) for unknown formats or bad JSON.
        Raises ErrUAPValidation / ErrUAPVersionUnsupported for the caller to
        decide whether to skip.
        """
        if isinstance(message.value, bytes):
            body = message.value.decode("utf-8")
        elif isinstance(message.value, str):
            body = message.value
        else:
            body = json.dumps(message.value)

        envelope = json.loads(body)

        if FIELD_UAP_VERSION in envelope:
            return UAPRecord.parse(envelope)
        elif "identity" in envelope:
            return UAPRecord.from_ingest_record(envelope)
        else:
            self.logger.warning(
                "internal.consumer.server: unknown message format, skipping",
                extra={"keys": list(envelope.keys())},
            )
            return None

    async def _handle_messages_batch(self, messages: List[KafkaMessage]) -> None:
        """Process a batch of Kafka messages through the full pipeline.

        Flow:
            Parse all messages → group valid UAPRecords by (project_id, domain)
            → for each group: ingest → asyncio.to_thread(pipeline.run)
                - normalization → dedup → spam → threads
                - NLP enrichment: batch ONNX inference for the whole group
            → async: persist each NLPFact → publish to contract topics

        Grouping by project_id lets NLPBatchEnricher call predict_batch()
        on N records at once instead of 1-by-1, amortising ONNX overhead.
        """
        if self.pipeline_usecase is None or self.ingestion_usecase is None:
            return

        # --- Parse all messages ---
        parsed: List[tuple] = []  # (project_id, domain_type_code, uap_record)
        for message in messages:
            try:
                uap_record = await self._parse_message(message)
                if uap_record is None:
                    continue

                project_id = uap_record.ingest.project_id if uap_record.ingest else None
                if not project_id:
                    continue

                parsed.append((project_id, uap_record.domain_type_code, uap_record))

            except (ErrUAPValidation, ErrUAPVersionUnsupported) as exc:
                self.logger.warning(
                    f"internal.consumer.server: UAP error (skipped): {exc}"
                )
            except json.JSONDecodeError as exc:
                self.logger.warning(
                    f"internal.consumer.server: bad JSON (skipped): {exc}"
                )
            except ValueError as exc:
                self.logger.warning(
                    f"internal.consumer.server: validation error (skipped): {exc}"
                )
            except Exception as exc:
                self.logger.error(
                    f"internal.consumer.server: parse error (skipped): {exc}"
                )

        if not parsed:
            return

        # --- Group by (project_id, domain_type_code) ---
        groups: dict[tuple, list] = {}
        for project_id, domain_type_code, uap_record in parsed:
            key = (project_id, domain_type_code)
            groups.setdefault(key, []).append(uap_record)

        # --- Process each group through the pipeline ---
        for (project_id, domain_type_code), uap_records in groups.items():
            try:
                domain_config = self.registry.domain_registry.lookup(domain_type_code)

                for uap_record in uap_records:
                    uap_record.raw["_resolved_domain_overlay"] = (
                        domain_config.contract_domain_overlay
                    )

                bundle, _stats = self.ingestion_usecase.from_kafka(
                    uap_records,
                    project_id=project_id,
                    campaign_id="",
                )
                if not bundle.records:
                    continue

                run_id = str(uuid.uuid4())

                # Set log enrichment context for this batch group
                set_trace_id(run_id)
                set_project_id(project_id)

                ctx = RunContext(
                    run_id=run_id,
                    project_id=project_id,
                    analysis_window_end=datetime.now(tz=timezone.utc),
                    ontology=domain_config.to_runtime_ontology(),
                )

                # CPU-bound: offload to thread pool.
                # NLPBatchEnricher.enrich_batch() will run batch ONNX here.
                # ContextVars are propagated automatically to asyncio.to_thread.
                result = await asyncio.to_thread(
                    self.pipeline_usecase.run,
                    bundle,
                    ctx,
                    self.pipeline_config,
                )

                self.logger.debug(
                    f"internal.consumer.server: batch pipeline run_id={result.run_id}, "
                    f"records={result.total_valid_records}, "
                    f"nlp_facts={len(result.nlp_facts)}, "
                    f"timings={result.stage_timings}"
                )

                if result.nlp_facts:
                    await self._persist_and_publish(result.nlp_facts)

            except Exception as exc:
                self.logger.error(
                    f"internal.consumer.server: pipeline failed for "
                    f"project={project_id}: {exc}"
                )
            finally:
                # Reset business context to avoid bleeding into next group
                clear_project_id()

    async def _handle_message(self, message: KafkaMessage) -> None:
        """Process a single Kafka message (kept for compatibility / fallback).

        Delegates to _handle_messages_batch() with a single-element list.
        """
        await self._handle_messages_batch([message])

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

            async def batch_handler(messages: List[KafkaMessage]) -> None:
                await self._handle_messages_batch(messages)

            await self.consumer.consume_batch(
                batch_handler,
                batch_size=10,
                timeout_ms=1000,
            )

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

            # Remove healthz file so readiness/liveness probes fail immediately,
            # ensuring no new traffic is routed to this pod during drain.
            try:
                self.HEALTHZ_FILE.unlink(missing_ok=True)
            except Exception:
                pass

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
