"""E2E test helpers: harness, message factories, and Kafka output consumers.

The ``E2ETestHarness`` is the central test driver. It wires:
  - Real KafkaProducer → real Kafka broker (testcontainers or KAFKA_BOOTSTRAP_SERVERS)
  - Real DomainRegistry (loaded from config/domains/)
  - Real ContractPublisherUseCase (same code-path as production)
  - Stub NLP (InsightMessage built directly — no PhoBERT / fasttext loaded)

This lets us test the full publish contract (3 topics, ordering, payload shape,
knowledge-srv gate conditions) without loading ML models.

Flow per test:
    1.  Start AIOKafkaConsumer on output topics BEFORE producing
    2.  Parse envelope via UAPRecord.from_ingest_record() (or legacy parse)
    3.  Domain-route: inject _resolved_domain_overlay into uap_record.raw
    4.  Build stub InsightMessage (configurable: should_index, sentiment, etc.)
    5.  ContractPublisherUseCase.publish_one() + flush() → Kafka
    6.  AIOKafkaConsumer polls output topics for up to POLL_TIMEOUT_S seconds
    7.  Return E2EResult with captured payloads per topic
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from aiokafka import AIOKafkaConsumer

from internal.contract_publisher.type import ContractPublishConfig
from internal.contract_publisher.usecase.new import New as NewContractPublisher
from internal.domain.loader import DomainLoader
from internal.model.insight_message import (
    InsightMessage,
    Project,
    Identity,
    Content,
    Business,
    BusinessImpact,
    BusinessEngagement,
    RAG,
    RAGIndex,
)
from internal.model.uap import ErrUAPValidation, ErrUAPVersionUnsupported, UAPRecord
from pkg.kafka.producer import KafkaProducer
from pkg.kafka.type import KafkaProducerConfig

# ---------------------------------------------------------------------------
# Topic constants (mirrors internal/contract_publisher/constant.py)
# ---------------------------------------------------------------------------

TOPIC_BATCH = "analytics.batch.completed"
TOPIC_INSIGHTS = "analytics.insights.published"
TOPIC_DIGEST = "analytics.report.digest"
OUTPUT_TOPICS = (TOPIC_BATCH, TOPIC_INSIGHTS, TOPIC_DIGEST)

# How long to wait (seconds) for Kafka output to arrive
POLL_TIMEOUT_S: float = 8.0
# Silence gap: stop polling once no message arrives within this window
SILENCE_GAP_S: float = 1.5


# ---------------------------------------------------------------------------
# E2EResult — what each test run returns
# ---------------------------------------------------------------------------


@dataclass
class E2EResult:
    """Captured Kafka output from one test run.

    Attributes:
        batch:         Parsed JSON payloads from analytics.batch.completed
        insights:      Parsed JSON payloads from analytics.insights.published
        digest:        Parsed JSON payloads from analytics.report.digest
        arrival_order: All messages in the order they arrived, as (topic, payload) tuples.
                       Useful for ordering assertions (batch before digest).
        error:         Set when the pipeline raised a known exception (parse error, etc.)
        raw_error:     The actual exception object (for asserting error type)
    """

    batch: list[dict] = field(default_factory=list)
    insights: list[dict] = field(default_factory=list)
    digest: list[dict] = field(default_factory=list)
    arrival_order: list[tuple[str, dict]] = field(default_factory=list)
    error: Optional[str] = None
    raw_error: Optional[Exception] = None

    # --- convenience properties ---

    @property
    def published(self) -> bool:
        """True if at least one message was captured on any output topic."""
        return bool(self.batch or self.insights or self.digest)

    @property
    def first_batch(self) -> Optional[dict]:
        return self.batch[0] if self.batch else None

    @property
    def first_digest(self) -> Optional[dict]:
        return self.digest[0] if self.digest else None


# ---------------------------------------------------------------------------
# Stub InsightMessage factory
# ---------------------------------------------------------------------------


def make_stub_insight(
    uap_record: UAPRecord,
    *,
    should_index: bool = True,
    sentiment_label: str = "NEUTRAL",
    sentiment_score: float = 0.0,
) -> InsightMessage:
    """Build a minimal InsightMessage for E2E testing.

    No NLP models are loaded — values are deterministic stubs.
    The critical fields for knowledge-srv gates are:
      - project.project_id  (batch gate: must be non-empty)
      - rag.index.should_index  (insights gate: gating RAG indexing)

    Engagement counts are propagated from uap_record.signals.engagement
    so tests can verify the full batch document contract.
    """
    text = uap_record.content.text or "stub text"
    eng = uap_record.signals.engagement if uap_record.signals else None
    return InsightMessage(
        event_id=uap_record.content.doc_id,
        project=Project(
            project_id=uap_record.ingest.project_id,
            entity_type="brand",
            entity_name="E2E Stub",
            brand="stub",
        ),
        identity=Identity(
            source_type=uap_record.ingest.source.source_type,
            source_id=uap_record.ingest.source.source_id,
            doc_id=uap_record.content.doc_id,
            doc_type=uap_record.content.doc_type,
            url=uap_record.content.url,
            language=uap_record.content.language,
            published_at=uap_record.content.published_at,
        ),
        content=Content(
            text=text,
            clean_text=text,
            summary=text[:120],
        ),
        business=Business(
            impact=BusinessImpact(
                engagement=BusinessEngagement(
                    like_count=eng.like_count if eng else 0,
                    comment_count=eng.comment_count if eng else 0,
                    share_count=eng.share_count if eng else 0,
                    view_count=eng.view_count if eng else 0,
                )
            )
        ),
        rag=RAG(
            index=RAGIndex(should_index=should_index),
        ),
    )


# ---------------------------------------------------------------------------
# Kafka output consumer helper
# ---------------------------------------------------------------------------


async def _collect_output(
    bootstrap_servers: str,
    *,
    group_id: str,
    timeout_s: float = POLL_TIMEOUT_S,
    gap_s: float = SILENCE_GAP_S,
) -> tuple[dict[str, list[dict]], list[tuple[str, dict]]]:
    """Start a fresh Kafka consumer, collect messages until silent.

    Uses auto_offset_reset='latest' so it only sees messages produced
    AFTER the consumer subscribes (i.e. produced during this test run).

    The consumer is started BEFORE the caller produces messages.
    This function should be called as a background task that the caller
    awaits AFTER producing. See E2ETestHarness.run() for the pattern.

    Returns:
        (per_topic, ordered) where:
          - per_topic: dict mapping topic → list of payloads
          - ordered:   list of (topic, payload) in arrival order
    """
    consumer = AIOKafkaConsumer(
        *OUTPUT_TOPICS,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        consumer_timeout_ms=int(gap_s * 1000),
        client_id=f"e2e-collector-{group_id}",
    )
    await consumer.start()

    captured: dict[str, list[dict]] = defaultdict(list)
    ordered: list[tuple[str, dict]] = []
    deadline = time.monotonic() + timeout_s

    try:
        while time.monotonic() < deadline:
            try:
                msg = await asyncio.wait_for(
                    consumer.getone(),
                    timeout=min(gap_s, deadline - time.monotonic()),
                )
                try:
                    payload = json.loads(msg.value.decode("utf-8"))
                except Exception:
                    payload = {"_raw": msg.value.decode("utf-8", errors="replace")}
                captured[msg.topic].append(payload)
                ordered.append((msg.topic, payload))
            except asyncio.TimeoutError:
                # Silence gap reached — no more messages expected
                break
    finally:
        await consumer.stop()

    return dict(captured), ordered


# ---------------------------------------------------------------------------
# E2ETestHarness
# ---------------------------------------------------------------------------


class E2ETestHarness:
    """Central test driver for analysis-srv E2E tests.

    Usage:
        harness = E2ETestHarness(bootstrap_servers="localhost:9092")
        await harness.start()

        result = await harness.run(envelope)   # happy path
        result = await harness.run_expecting_error(bad_envelope)  # error cases

        await harness.stop()

    For fixture use, prefer the ``harness`` pytest fixture in conftest.py.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer: Optional[KafkaProducer] = None
        self._publisher = None
        self._domain_registry = None

    async def start(self) -> None:
        """Wire up real Kafka producer + real domain registry."""
        self._domain_registry = DomainLoader.load_from_dir(
            "config/domains", fallback_code="_default"
        )
        self._producer = KafkaProducer(
            KafkaProducerConfig(
                bootstrap_servers=self.bootstrap_servers,
                client_id="e2e-test-producer",
            )
        )
        await self._producer.start()
        self._publisher = NewContractPublisher(
            kafka_producer=self._producer,
            config=ContractPublishConfig(batch_size=1),  # flush after every record
        )

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    # --- Core run methods ---

    async def run(
        self,
        envelope: dict,
        *,
        should_index: bool = True,
        sentiment_label: str = "NEUTRAL",
        sentiment_score: float = 0.0,
    ) -> E2EResult:
        """Run the full pipeline for one ingest-srv flat-format envelope.

        Steps:
          1. Start output consumer (before producing — ensures no messages missed)
          2. Parse envelope → UAPRecord
          3. Domain-route → inject _resolved_domain_overlay
          4. Publish via ContractPublisher
          5. Collect output from Kafka and return as E2EResult
        """
        group_id = f"e2e-{uuid.uuid4()}"

        # 1. Start consumer FIRST (latest offset) — subscribe before we produce
        consumer_task = asyncio.create_task(
            _collect_output(
                self.bootstrap_servers,
                group_id=group_id,
            )
        )

        # Brief pause to let consumer join and commit initial offsets
        await asyncio.sleep(1.2)

        try:
            # 2. Parse
            uap_record = UAPRecord.from_ingest_record(envelope)

            # 3. Domain routing
            domain_cfg = self._domain_registry.lookup(uap_record.domain_type_code)
            uap_record.raw["_resolved_domain_overlay"] = (
                domain_cfg.contract_domain_overlay
            )

            # 4. Build stub insight + publish
            insight = make_stub_insight(
                uap_record,
                should_index=should_index,
                sentiment_label=sentiment_label,
                sentiment_score=sentiment_score,
            )
            await self._publisher.publish_one(uap=uap_record, msg=insight)
            await self._publisher.flush()

        except (ErrUAPValidation, ErrUAPVersionUnsupported, ValueError) as exc:
            # Known pipeline errors — cancel consumer, return error result
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass
            return E2EResult(error=type(exc).__name__, raw_error=exc)

        # 5. Collect output
        captured, ordered = await consumer_task
        return E2EResult(
            batch=captured.get(TOPIC_BATCH, []),
            insights=captured.get(TOPIC_INSIGHTS, []),
            digest=captured.get(TOPIC_DIGEST, []),
            arrival_order=ordered,
        )

    async def run_legacy(
        self,
        envelope: dict,
        *,
        should_index: bool = True,
    ) -> E2EResult:
        """Run the pipeline with a legacy UAP-format envelope (has uap_version)."""
        group_id = f"e2e-{uuid.uuid4()}"
        consumer_task = asyncio.create_task(
            _collect_output(self.bootstrap_servers, group_id=group_id)
        )
        await asyncio.sleep(1.2)

        try:
            uap_record = UAPRecord.parse(envelope)
            domain_cfg = self._domain_registry.lookup(
                uap_record.raw.get("domain_type_code", "")
            )
            uap_record.raw["_resolved_domain_overlay"] = (
                domain_cfg.contract_domain_overlay
            )

            insight = make_stub_insight(uap_record, should_index=should_index)
            await self._publisher.publish_one(uap=uap_record, msg=insight)
            await self._publisher.flush()

        except (ErrUAPValidation, ErrUAPVersionUnsupported, ValueError) as exc:
            consumer_task.cancel()
            try:
                await consumer_task
            except (asyncio.CancelledError, Exception):
                pass
            return E2EResult(error=type(exc).__name__, raw_error=exc)

        captured, ordered = await consumer_task
        return E2EResult(
            batch=captured.get(TOPIC_BATCH, []),
            insights=captured.get(TOPIC_INSIGHTS, []),
            digest=captured.get(TOPIC_DIGEST, []),
            arrival_order=ordered,
        )

    async def run_bytes(self, raw_bytes: bytes) -> E2EResult:
        """Run with raw bytes — for testing malformed JSON, empty body, etc."""
        try:
            envelope = json.loads(raw_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return E2EResult(error=type(exc).__name__, raw_error=exc)
        return await self.run(envelope)

    async def run_no_output_check(self, raw_bytes: bytes) -> E2EResult:
        """Run and wait a fixed timeout, expecting no output.

        Useful for testing that bad inputs produce zero Kafka messages.
        """
        group_id = f"e2e-{uuid.uuid4()}"

        # Start consumer first
        consumer_task = asyncio.create_task(
            _collect_output(
                self.bootstrap_servers,
                group_id=group_id,
                timeout_s=4.0,
                gap_s=2.0,
            )
        )
        await asyncio.sleep(1.2)

        # Try to run — errors are swallowed (we just care about no output)
        try:
            envelope = json.loads(raw_bytes)
            if "identity" in envelope:
                uap_record = UAPRecord.from_ingest_record(envelope)
                domain_cfg = self._domain_registry.lookup(uap_record.domain_type_code)
                uap_record.raw["_resolved_domain_overlay"] = (
                    domain_cfg.contract_domain_overlay
                )
                insight = make_stub_insight(uap_record)
                await self._publisher.publish_one(uap=uap_record, msg=insight)
                await self._publisher.flush()
        except Exception:
            pass  # expected — we verify no Kafka output below

        captured, ordered = await consumer_task
        return E2EResult(
            batch=captured.get(TOPIC_BATCH, []),
            insights=captured.get(TOPIC_INSIGHTS, []),
            digest=captured.get(TOPIC_DIGEST, []),
            arrival_order=ordered,
        )


# ---------------------------------------------------------------------------
# Ingest-srv envelope factories
# ---------------------------------------------------------------------------


def make_ingest_envelope(
    *,
    project_id: str = "proj-e2e-001",
    uap_id: str | None = None,
    uap_type: str = "post",
    platform: str = "facebook",
    origin_id: str = "fb-123",
    url: str = "https://fb.com/posts/123",
    task_id: str = "task-e2e-001",
    text: str = "Xe VinFast VF8 chạy êm, pin bền, rất hài lòng!",
    language: str = "vi",
    posted_at: str = "2024-03-01T08:00:00Z",
    ingested_at: str = "2024-03-01T08:05:00Z",
    author_id: str = "author-001",
    nickname: str = "Người dùng test",
    username: str = "testuser",
    is_verified: bool = False,
    likes: int = 50,
    comments_count: int = 10,
    shares: int = 3,
    views: int = 500,
    saves: int = 2,
    domain_type_code: str = "vinfast",
    crawl_keyword: str = "vinfast vf8",
    parent_id: str | None = None,
    media: list[dict] | None = None,
    platform_meta: dict | None = None,
) -> dict:
    """Build a fully-formed ingest-srv flat-format envelope for E2E tests."""
    if uap_id is None:
        uap_id = f"uap-{uuid.uuid4().hex[:12]}"

    return {
        "identity": {
            "uap_id": uap_id,
            "uap_type": uap_type,
            "platform": platform,
            "origin_id": origin_id,
            "url": url,
            "task_id": task_id,
            "project_id": project_id,
        },
        "hierarchy": {
            "parent_id": parent_id,
            "root_id": None,
            "depth": 0 if parent_id is None else 1,
        },
        "content": {
            "text": text,
            "language": language,
        },
        "author": {
            "id": author_id,
            "nickname": nickname,
            "username": username,
            "avatar": None,
            "is_verified": is_verified,
        },
        "engagement": {
            "likes": likes,
            "comments_count": comments_count,
            "shares": shares,
            "views": views,
            "saves": saves,
            "reply_count": 0,
        },
        "media": media or [],
        "temporal": {
            "posted_at": posted_at,
            "updated_at": None,
            "ingested_at": ingested_at,
        },
        "domain_type_code": domain_type_code,
        "crawl_keyword": crawl_keyword,
        "platform_meta": platform_meta or {},
    }


def make_legacy_uap_envelope(
    *,
    project_id: str = "proj-e2e-001",
    uap_id: str | None = None,
) -> dict:
    """Build a minimal legacy UAP envelope (has uap_version field)."""
    if uap_id is None:
        uap_id = f"uap-{uuid.uuid4().hex[:12]}"

    return {
        "uap_version": "1.0",
        "event_id": uap_id,
        "ingest": {
            "project_id": project_id,
            "source": {"source_id": "fb-legacy", "source_type": "facebook"},
            "batch": {"received_at": "2024-03-01T08:05:00Z"},
            "trace": {"mapping_id": "task-legacy"},
        },
        "content": {
            "doc_id": uap_id,
            "doc_type": "post",
            "text": "Legacy UAP format test post",
            "language": "vi",
        },
        "signals": {
            "engagement": {
                "like_count": 10,
                "comment_count": 2,
                "share_count": 1,
                "view_count": 100,
                "save_count": 0,
            }
        },
        "context": {"keywords_matched": ["test"]},
    }
