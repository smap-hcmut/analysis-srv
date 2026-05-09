import asyncio
import dataclasses
import json
import os
import time
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
        self._crisis_alert_topic = os.getenv("ANALYTICS_CRISIS_ALERT_TOPIC", "analytics.crisis.alert")
        self._last_crisis_runtime_status: dict[str, tuple[str, float]] = {}
        self._domain_pipeline_config_cache: dict[str, object] = {}
        self._crisis_runtime_state_prefix = "smap:crisis:runtime-state"
        self._crisis_runtime_lock_prefix = "smap:crisis:runtime-lock"

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
                crisis_runtime_config = await self._get_crisis_runtime_config(project_id)
                if crisis_runtime_config is not None:
                    pipeline_config = dataclasses.replace(
                        pipeline_config,
                        crisis_config=crisis_runtime_config.crisis_config,
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

                await self._maybe_apply_crisis_runtime(result, crisis_runtime_config)
                await self._maybe_publish_crisis_alert(result, crisis_runtime_config)

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
        if normalized == "watch":
            return "WATCH"
        if normalized == "none":
            return "NONE"
        return "NORMAL"

    async def _get_crisis_runtime_config(self, project_id: str):
        if self.project_service_client is None:
            return None
        try:
            return await self.project_service_client.get_crisis_runtime_config(project_id)
        except Exception as exc:
            self.logger.warning(
                "Failed to fetch crisis runtime config; falling back to defaults",
                extra={"project_id": project_id, "error": str(exc)},
            )
            return None

    async def _maybe_apply_crisis_runtime(self, result, runtime_config=None) -> None:
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
        cooldown_seconds = self._adaptive_cooldown_seconds(runtime_config)
        last_status, last_updated_at = await self._get_crisis_runtime_state(project_id)

        if last_status == target_status:
            return

        now = time.time()
        if last_updated_at is not None and now - last_updated_at < cooldown_seconds:
            return

        lock_token = await self._acquire_crisis_runtime_lock(project_id)
        if lock_token is None:
            return

        run_id = str(getattr(assessment, "run_id", ""))
        score = float(getattr(assessment, "composite_crisis_score", 0.0) or 0.0)
        reason = (
            f"analysis auto-apply: level={crisis_level.lower()} score={score:.2f}"
        )
        event_ref = f"analysis-run:{run_id}" if run_id else ""

        try:
            last_status, last_updated_at = await self._get_crisis_runtime_state(project_id)
            if last_status == target_status:
                return
            if last_updated_at is not None and time.time() - last_updated_at < cooldown_seconds:
                return

            output = await self.project_service_client.apply_crisis_runtime(
                project_id,
                crisis_level=target_status,
                reason=reason,
                event_ref=event_ref,
            )
            await self._set_crisis_runtime_state(project_id, target_status)
            self.logger.info(
                "Crisis runtime applied",
                extra={
                    "project_id": output.project_id,
                    "crisis_status": output.crisis_status,
                    "crisis_level": output.crisis_level,
                    "applied_crawl_mode": output.applied_crawl_mode,
                    "affected_datasources": output.affected_datasource_count,
                    "noop_reason": output.noop_reason,
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
        finally:
            await self._release_crisis_runtime_lock(project_id, lock_token)

    async def _get_crisis_runtime_state(self, project_id: str) -> tuple[str | None, float | None]:
        redis_entry = await self._get_redis_crisis_runtime_state(project_id)
        if redis_entry is not None:
            return redis_entry

        local_entry = self._last_crisis_runtime_status.get(project_id)
        if local_entry is None:
            return None, None
        return local_entry

    async def _get_redis_crisis_runtime_state(self, project_id: str) -> tuple[str | None, float | None] | None:
        redis = getattr(self.deps, "redis", None)
        if redis is None:
            return None
        try:
            value = await redis.get_json(self._crisis_runtime_state_key(project_id))
        except Exception:
            return None
        if not isinstance(value, dict):
            return None

        status = str(value.get("status") or "").strip().upper() or None
        updated_at_raw = value.get("updated_at")
        try:
            updated_at = float(updated_at_raw) if updated_at_raw is not None else None
        except (TypeError, ValueError):
            updated_at = None
        return status, updated_at

    async def _set_crisis_runtime_state(self, project_id: str, target_status: str) -> None:
        now = time.time()
        self._last_crisis_runtime_status[project_id] = (target_status, now)

        redis = getattr(self.deps, "redis", None)
        if redis is None:
            return
        try:
            await redis.set(
                self._crisis_runtime_state_key(project_id),
                {"status": target_status, "updated_at": now},
            )
        except Exception:
            return

    async def _acquire_crisis_runtime_lock(self, project_id: str) -> str | None:
        redis = getattr(self.deps, "redis", None)
        client = getattr(redis, "client", None)
        if client is None:
            return ""
        token = uuid.uuid4().hex
        try:
            acquired = await client.set(
                self._crisis_runtime_lock_key(project_id),
                token,
                ex=45,
                nx=True,
            )
            return token if acquired else None
        except Exception:
            return ""

    async def _release_crisis_runtime_lock(self, project_id: str, token: str | None) -> None:
        if not token:
            return
        redis = getattr(self.deps, "redis", None)
        client = getattr(redis, "client", None)
        if client is None:
            return
        key = self._crisis_runtime_lock_key(project_id)
        try:
            current = await client.get(key)
            if current == token:
                await client.delete(key)
        except Exception:
            return

    def _crisis_runtime_state_key(self, project_id: str) -> str:
        return f"{self._crisis_runtime_state_prefix}:{project_id}"

    def _crisis_runtime_lock_key(self, project_id: str) -> str:
        return f"{self._crisis_runtime_lock_prefix}:{project_id}"

    @staticmethod
    def _adaptive_cooldown_seconds(runtime_config=None) -> float:
        crisis_config = getattr(runtime_config, "crisis_config", {}) if runtime_config else {}
        response_policy = crisis_config.get("response_policy") if isinstance(crisis_config, dict) else {}
        adaptive = response_policy.get("adaptive_crawl") if isinstance(response_policy, dict) else {}
        minutes = adaptive.get("cooldown_minutes") if isinstance(adaptive, dict) else 30
        try:
            return max(float(minutes), 1.0) * 60.0
        except (TypeError, ValueError):
            return 30.0 * 60.0

    async def _maybe_publish_crisis_alert(self, result, runtime_config=None) -> None:
        if self.deps.kafka_producer is None or not self.deps.kafka_producer.is_running():
            return

        assessment = getattr(result, "crisis_assessment", None)
        if assessment is None:
            return

        level = str(getattr(assessment, "crisis_level", "none")).lower()
        if level == "none":
            return

        crisis_config = getattr(runtime_config, "crisis_config", {}) if runtime_config else {}
        response_policy = crisis_config.get("response_policy") if isinstance(crisis_config, dict) else {}
        notification_policy = response_policy.get("notification") if isinstance(response_policy, dict) else {}
        if isinstance(notification_policy, dict) and notification_policy.get("enabled") is False:
            return

        trigger_level = str(
            notification_policy.get("trigger_level") if isinstance(notification_policy, dict) else "WARNING"
        ).lower() or "warning"
        if self._level_rank(level) < self._level_rank(trigger_level):
            return

        project_id = str(getattr(assessment, "project_id", "")).strip()
        if not project_id:
            return

        project_name = str(getattr(runtime_config, "project_name", "") or project_id)
        owner_user_id = str(getattr(runtime_config, "owner_user_id", "") or "")
        if not owner_user_id:
            self.logger.warning(
                "Skipping crisis alert without owner user",
                extra={"project_id": project_id, "level": level},
            )
            return

        signals = list(getattr(assessment, "signals", []) or [])
        affected = []
        sample_mentions = []
        for signal in signals:
            signal_type = str(getattr(signal, "signal_type", "") or "")
            if signal_type:
                affected.append(signal_type)
            for ref in getattr(signal, "evidence_references", []) or []:
                sample_mentions.append(str(ref))

        score = float(getattr(assessment, "composite_crisis_score", 0.0) or 0.0)
        threshold = self._alert_threshold_for_level(trigger_level)
        repeat_cooldown_minutes = 60
        ops_alert = level == "critical"
        if isinstance(notification_policy, dict):
            try:
                repeat_cooldown_minutes = max(
                    int(notification_policy.get("repeat_cooldown_minutes", repeat_cooldown_minutes)),
                    1,
                )
            except (TypeError, ValueError):
                repeat_cooldown_minutes = 60
            ops_alert = bool(notification_policy.get("ops_alert_on_critical", True)) and level == "critical"

        title = f"{project_name}: {level.upper()} brand risk"
        message = f"SMAP detected {level} crisis signals for {project_name} (score {score:.2f})."
        run_id = str(getattr(assessment, "run_id", "") or "")

        payload = {
            "alert_type": "CRISIS_ALERT",
            "project_id": project_id,
            "project_name": project_name,
            "campaign_id": str(getattr(runtime_config, "campaign_id", "") or ""),
            "user_id": owner_user_id,
            "severity": "critical" if level == "critical" else "warning",
            "level": level.upper(),
            "metric": "composite_crisis_score",
            "current_value": score,
            "threshold": threshold,
            "affected_aspects": affected[:8],
            "sample_mentions": sample_mentions[:5],
            "time_window": "current analysis batch",
            "action_required": "Review negative drivers, align response owner, and monitor crawl acceleration.",
            "run_id": run_id,
            "title": title,
            "message": message,
            "repeat_cooldown_minutes": repeat_cooldown_minutes,
            "ops_alert": ops_alert,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        try:
            await self.deps.kafka_producer.send_json(
                topic=self._crisis_alert_topic,
                value=payload,
                key=project_id,
            )
            self.logger.info(
                "Crisis alert published",
                extra={"project_id": project_id, "level": level, "topic": self._crisis_alert_topic},
            )
        except Exception as exc:
            self.logger.error(
                "Crisis alert publish failed",
                extra={"project_id": project_id, "level": level, "error": str(exc)},
            )

    @staticmethod
    def _level_rank(level: str) -> int:
        normalized = str(level).strip().lower()
        if normalized == "critical":
            return 4
        if normalized == "warning":
            return 3
        if normalized == "watch":
            return 2
        if normalized == "normal":
            return 1
        return 0

    @staticmethod
    def _alert_threshold_for_level(level: str) -> float:
        normalized = str(level).strip().lower()
        if normalized == "critical":
            return 5.0
        if normalized == "watch":
            return 0.8
        return 2.5

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
