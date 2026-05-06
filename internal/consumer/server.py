import asyncio
import dataclasses
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
from internal.analytics.usecase.batch_enricher import enrich_nlp_facts_with_bundle
from pkg.logger.logger import set_trace_id, set_project_id, clear_project_id
from internal.http.project_client import build_project_service_client
from internal.enrichment.type import EnricherConfig
from internal.enrichment.usecase.usecase import EnrichmentUseCase

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

        self.project_service_client = None
        self._crisis_runtime_apply_enabled = self._env_enabled(
            os.getenv("ANALYTICS_ENABLE_CRISIS_RUNTIME_APPLY", "false")
        )
        self._last_crisis_runtime_status: dict[str, str] = {}
        self._domain_pipeline_config_cache: dict[str, object] = {}

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

            if self._crisis_runtime_apply_enabled:
                try:
                    self.project_service_client = build_project_service_client()
                    self.logger.info(
                        "Crisis runtime auto-apply enabled",
                        extra={
                            "feature": "crisis_runtime_apply",
                            "mode": "project_service_internal_api",
                        },
                    )
                except Exception as exc:
                    self.logger.error(
                        "Failed to initialize crisis runtime client; feature disabled",
                        extra={"error": str(exc)},
                    )
                    self._crisis_runtime_apply_enabled = False

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

        Returns None (with a debug/info log) for unknown formats or bad JSON.
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
            self.logger.info(
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
                self.logger.info(
                    f"internal.consumer.server: UAP error (skipped): {exc}"
                )
            except json.JSONDecodeError as exc:
                self.logger.info(
                    f"internal.consumer.server: bad JSON (skipped): {exc}"
                )
            except ValueError as exc:
                self.logger.info(
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
                pipeline_config = self._resolve_pipeline_config_for_domain(
                    domain_config.domain_code
                )

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
                    pipeline_config,
                )

                self.logger.debug(
                    f"internal.consumer.server: batch pipeline run_id={result.run_id}, "
                    f"records={result.total_valid_records}, "
                    f"nlp_input_records={result.nlp_input_records}, "
                    f"nlp_facts={len(result.nlp_facts)}, "
                    f"filtered_unsupported_language={result.filtered_out_unsupported_language}, "
                    f"timings={result.stage_timings}"
                )

                await self._maybe_apply_crisis_runtime(result)

                if result.nlp_facts:
                    enrich_nlp_facts_with_bundle(
                        result.nlp_facts,
                        result.enrichment_bundle,
                    )
                    await self._persist_and_publish(
                        result.nlp_facts,
                        result.enrichment_bundle,
                    )

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

    async def _persist_and_publish(self, nlp_facts: list, enrichment_bundle=None) -> None:
        """Persist each NLPFact to post_insight and publish to contract topics.

        Non-fatal — errors are logged per-record; a single failure does not
        prevent the remaining facts from being persisted/published.
        """
        for nlp_fact in nlp_facts:
            # Persist to post_insight
            if self.post_insight_usecase and nlp_fact.analytics_result is not None:
                try:
                    pi_input = NLPBatchEnricher.to_post_insight_input(
                        nlp_fact,
                        enrichment_bundle,
                    )
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
            batch_size = int(os.getenv("ANALYTICS_CONSUME_BATCH_SIZE", "6"))
            timeout_ms = int(os.getenv("ANALYTICS_CONSUME_TIMEOUT_MS", "1000"))
            if batch_size < 1:
                batch_size = 1
            if timeout_ms < 100:
                timeout_ms = 100

            self.logger.info(
                "Kafka consume loop config",
                extra={"batch_size": batch_size, "timeout_ms": timeout_ms},
            )

            async def batch_handler(messages: List[KafkaMessage]) -> None:
                await self._handle_messages_batch(messages)

            await self.consumer.consume_batch(
                batch_handler,
                batch_size=batch_size,
                timeout_ms=timeout_ms,
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

            if self.project_service_client is not None:
                await self.project_service_client.close()

            self.logger.info("Kafka consumer server shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.logger.exception("Shutdown error:")

    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def _env_enabled(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _map_crisis_level_to_status(level: str) -> str:
        normalized = level.strip().lower()
        if normalized == "critical":
            return "CRITICAL"
        if normalized == "warning":
            return "WARNING"
        return "NORMAL"

    async def _maybe_apply_crisis_runtime(self, result) -> None:
        if not self._crisis_runtime_apply_enabled:
            return
        if self.project_service_client is None:
            return

        assessment = getattr(result, "crisis_assessment", None)
        if assessment is None:
            return

        project_id = str(getattr(assessment, "project_id", "")).strip()
        if not project_id:
            return

        crisis_level = str(getattr(assessment, "crisis_level", "none"))
        target_status = self._map_crisis_level_to_status(crisis_level)
        last_status = self._last_crisis_runtime_status.get(project_id)

        # Avoid noisy no-op calls on initial NORMAL state when no prior runtime
        # transition has been applied for this project.
        if last_status is None and target_status == "NORMAL":
            return

        if last_status == target_status:
            return

        run_id = str(getattr(assessment, "run_id", ""))
        score = float(getattr(assessment, "composite_crisis_score", 0.0) or 0.0)
        reason = (
            f"analysis auto-apply: level={crisis_level.lower()} score={score:.2f}"
        )
        event_ref = f"analysis-run:{run_id}" if run_id else ""

        try:
            output = await self.project_service_client.apply_crisis_runtime(
                project_id,
                status=target_status,
                reason=reason,
                event_ref=event_ref,
            )
            self._last_crisis_runtime_status[project_id] = target_status
            self.logger.info(
                "Crisis runtime applied",
                extra={
                    "project_id": output.project_id,
                    "crisis_status": output.crisis_status,
                    "applied_crawl_mode": output.applied_crawl_mode,
                    "affected_datasources": output.affected_datasource_count,
                },
            )
        except Exception as exc:
            self.logger.error(
                "Crisis runtime apply failed",
                extra={
                    "project_id": project_id,
                    "target_status": target_status,
                    "error": str(exc),
                },
            )

    def _resolve_pipeline_config_for_domain(self, domain_code: str):
        if self.pipeline_config is None or self.registry is None:
            return self.pipeline_config

        resolved_code = (domain_code or "").strip() or "_default"
        cached = self._domain_pipeline_config_cache.get(resolved_code)
        if cached is not None:
            return cached

        try:
            domain_cfg = self.registry.domain_registry.lookup(resolved_code)
            ontology_registry = domain_cfg.load_ontology_registry()

            enrichment_cfg = EnricherConfig(
                entity_enabled=self.deps.config.enrichment.entity_enabled,
                semantic_enabled=self.deps.config.enrichment.semantic_enabled,
                topic_enabled=self.deps.config.enrichment.topic_enabled,
                source_influence_enabled=self.deps.config.enrichment.source_influence_enabled,
                semantic_full_enabled=self.deps.config.enrichment.semantic_full_enabled,
            )
            enrichment_uc = EnrichmentUseCase(
                config=enrichment_cfg,
                ontology_registry=ontology_registry,
            )

            services = dataclasses.replace(
                self.pipeline_config.services,
                ontology_registry=ontology_registry,
                enrichment=enrichment_uc,
            )
            cfg = dataclasses.replace(self.pipeline_config, services=services)
            self._domain_pipeline_config_cache[resolved_code] = cfg
            return cfg
        except Exception as exc:
            self.logger.error(
                "Failed to resolve domain pipeline config, fallback to default",
                extra={"domain_code": resolved_code, "error": str(exc)},
            )
            return self.pipeline_config


__all__ = ["ConsumerServer"]
