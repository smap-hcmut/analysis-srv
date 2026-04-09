"""ContractPublisherUseCase — buffer + auto-flush for all 3 contract topics.

Workflow per document:
    AnalyticsProcess._publish_enriched()
        → contract_publisher.publish_one(uap, msg)
            → buffer.append((uap, msg))
            → if len(buffer) >= batch_size: await self.flush()

Flush sequence (enforced by publish_order.py):
    1. analytics.batch.completed
    2. analytics.insights.published  (0 cards in Phase 1)
    3. analytics.report.digest       (minimal — total count only until Phase 5)
"""

from typing import Any, Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage
from internal.contract_publisher.type import (
    ContractPublishConfig,
    RunContext,
    PublishOutput,
)
from internal.contract_publisher.errors import ContractPublishError
from internal.runtime.usecase.run_id import default_run_id
from .publish_batch import build_batch_completed_payload
from .publish_insights import build_insights_published_payloads
from .publish_digest import build_report_digest_payload
from .publish_order import publish_in_required_order
from .helpers import (
    normalize_platform_lower,
    min_iso_utc,
    max_iso_utc,
    now_iso_utc,
)


class ContractPublisherUseCase:
    """Buffers (UAPRecord, InsightMessage) pairs and flushes to 3 Kafka topics."""

    def __init__(
        self,
        kafka_producer: IKafkaProducer,
        config: ContractPublishConfig,
        logger: Optional[Logger] = None,
    ):
        self._producer = kafka_producer
        self._config = config
        self._logger = logger
        self._buffer: list[tuple[UAPRecord, InsightMessage]] = []

    async def publish_one(
        self,
        uap: UAPRecord,
        msg: InsightMessage,
        insight_cards: Optional[list[Any]] = None,
    ) -> None:
        """Buffer one document. Auto-flushes when batch_size is reached.

        Args:
            uap:           Original UAPRecord (needed for media_type derivation).
            msg:           Built InsightMessage from builder.
            insight_cards: Reserved for Phase 4+; ignored in Phase 1.
        """
        if not self._config.enabled:
            return

        self._buffer.append((uap, msg))

        if len(self._buffer) >= self._config.batch_size:
            await self.flush()

    async def flush(
        self,
        ctx: Optional[RunContext] = None,
        insight_cards: Optional[list[Any]] = None,
        bi_report_bundle: Optional[Any] = None,
    ) -> PublishOutput:
        """Drain buffer and publish batch.completed → insights → digest.

        Args:
            ctx:               If provided, used as-is. Otherwise derived from buffer.
            insight_cards:     InsightCard list for Layer 2 (Phase 4+).
            bi_report_bundle:  BIReportBundle for enriched Layer 1 (Phase 5+).

        Returns:
            PublishOutput with success/failure details.
        """
        if not self._buffer:
            return PublishOutput(success=True, documents_published=0)

        if not self._config.enabled:
            self._buffer.clear()
            return PublishOutput(success=True, documents_published=0)

        batch = self._buffer.copy()
        self._buffer.clear()

        if ctx is None:
            ctx = self._build_ctx_from_batch(batch)

        try:
            # Layer 3
            batch_payload = build_batch_completed_payload(batch, ctx)

            # Layer 2 — empty in Phase 1
            cards = insight_cards or []
            insight_payloads = build_insights_published_payloads(cards, ctx)

            # Layer 1 — minimal digest (total_mentions only) until Phase 5
            digest_payload = build_report_digest_payload(
                ctx=ctx,
                total_mentions=len(batch),
                bi_report_bundle=bi_report_bundle,
            )

            await publish_in_required_order(
                batch_payload=batch_payload,
                insight_payloads=insight_payloads,
                digest_payload=digest_payload,
                kafka_producer=self._producer,
                logger=self._logger,
            )

            return PublishOutput(
                success=True,
                documents_published=len(batch_payload.get("documents", [])),
                insights_published=len(insight_payloads),
            )

        except ContractPublishError as exc:
            # Re-add to buffer for retry on next flush
            self._buffer = batch + self._buffer
            if self._logger:
                self._logger.error(
                    f"internal.contract_publisher.usecase: flush failed, "
                    f"re-queued {len(batch)} documents: {exc}"
                )
            return PublishOutput(success=False, error_message=str(exc))

        except Exception as exc:
            # Unexpected error — don't re-queue, log and return failure
            if self._logger:
                self._logger.error(
                    f"internal.contract_publisher.usecase: unexpected flush error: {exc}"
                )
            return PublishOutput(success=False, error_message=str(exc))

    async def close(self) -> None:
        """Final flush on shutdown. Best-effort — logs but does not raise."""
        if self._buffer:
            if self._logger:
                self._logger.info(
                    f"internal.contract_publisher.usecase: closing with "
                    f"{len(self._buffer)} buffered documents — flushing"
                )
            try:
                await self.flush()
            except Exception as exc:
                if self._logger:
                    self._logger.error(
                        f"internal.contract_publisher.usecase: close flush failed: {exc}"
                    )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_ctx_from_batch(
        self, batch: list[tuple[UAPRecord, InsightMessage]]
    ) -> RunContext:
        """Derive RunContext from buffer contents.

        - project_id:   first record's ingest.project_id
        - campaign_id:  first record's context.campaign_id (or "")
        - platform:     first record's source.source_type → lowercase
        - domain_overlay: from config
        - window_start/end: min/max of content.published_at across batch
        """
        first_uap = batch[0][0] if batch else None

        project_id = ""
        campaign_id = ""
        source_type = ""

        if first_uap:
            project_id = (first_uap.ingest.project_id if first_uap.ingest else "") or ""
            campaign_id = (
                first_uap.context.campaign_id if first_uap.context else ""
            ) or ""
            source_type = (
                first_uap.ingest.source.source_type
                if first_uap.ingest and first_uap.ingest.source
                else ""
            ) or ""

        # Collect published_at timestamps for window derivation
        timestamps = [
            uap.content.published_at or ""
            for uap, _ in batch
            if uap.content and uap.content.published_at
        ]
        window_start = min_iso_utc(timestamps) if timestamps else now_iso_utc()
        window_end = max_iso_utc(timestamps) if timestamps else now_iso_utc()

        return RunContext(
            run_id=default_run_id(),
            project_id=project_id,
            campaign_id=campaign_id,
            platform=normalize_platform_lower(source_type),
            domain_overlay=self._config.domain_overlay,
            analysis_window_start=window_start,
            analysis_window_end=window_end,
        )


__all__ = ["ContractPublisherUseCase"]
