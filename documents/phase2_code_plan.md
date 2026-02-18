# Phase 2: Code Plan — Output Layer Refactoring (Enriched Output + Kafka Publisher)

**Ref:** `documents/master-proposal.md` (Phase 2)
**Convention:** `documents/convention/`
**Output Spec:** `refactor_plan/input-output/ouput/output_example.json`, `refactor_plan/indexing_input_schema.md`
**Data Mapping:** `refactor_plan/04_data_mapping.md`
**Depends on:** Phase 1 (UAP Parser — done)

---

## 1. SCOPE

Sau khi pipeline xử lý xong, build Enriched Output JSON từ UAP Input + AI Result, publish batch lên Kafka topic `smap.analytics.output`.

**Boundary:**

- IN: ResultBuilder (transform), Kafka publish logic, pipeline integration (gọi builder + publish sau DB save)
- OUT: Business logic mới (Phase 4), DB schema migration (Phase 3), AI model changes

---

## 2. FILE PLAN

### 2.1 Files tạo mới

| # | File | Vai trò (Convention ref) |
|---|------|--------------------------|
| 1 | `internal/model/enriched_output.py` | System-level Enriched Output dataclasses. Output contract chung cross-service, đặt trong `internal/model/` (`convention_python.md` §1). |
| 2 | `internal/builder/__init__.py` | Builder domain module init + exports. |
| 3 | `internal/builder/interface.py` | `IResultBuilder` Protocol (`convention_python.md` §2: Protocol + `@runtime_checkable`). |
| 4 | `internal/builder/type.py` | Builder Input/Output types (`convention_python.md` §1: types trong `type.py`). |
| 5 | `internal/builder/errors.py` | Builder-specific errors (`convention_python.md` §2: prefix `Err`). |
| 6 | `internal/builder/constant.py` | Builder constants (enriched_version, snippet length, etc.). |
| 7 | `internal/builder/usecase/__init__.py` | Usecase re-exports. |
| 8 | `internal/builder/usecase/new.py` | Factory `New()` (`convention_python.md` §4: factory only). |
| 9 | `internal/builder/usecase/build.py` | Core build logic: UAP + AnalyticsResult → EnrichedOutput (`convention_usecase.md` §2.1: one file one method). |
| 10 | `internal/builder/usecase/helpers.py` | Private helpers: snippet builder, timestamp formatter, etc. (`convention_usecase.md` §2.1: ALL helpers in helpers.py). |
| 11 | `internal/analytics/delivery/kafka/__init__.py` | Kafka delivery module init. |
| 12 | `internal/analytics/delivery/kafka/producer/__init__.py` | Kafka producer delivery init. |
| 13 | `internal/analytics/delivery/kafka/producer/new.py` | Factory: tạo analytics Kafka publisher. |
| 14 | `internal/analytics/delivery/kafka/producer/publisher.py` | `AnalyticsPublisher`: accumulate batch + publish array to Kafka. |
| 15 | `internal/analytics/delivery/kafka/producer/type.py` | Delivery DTOs cho Kafka publish. |
| 16 | `internal/analytics/delivery/kafka/producer/constant.py` | Kafka topic name, batch size defaults. |

### 2.2 Files sửa

| # | File | Thay đổi |
|---|------|----------|
| 17 | `internal/analytics/usecase/usecase.py` | Sau DB save → gọi ResultBuilder.build() → gọi Publisher.publish(). Thêm dependencies. |
| 18 | `internal/analytics/usecase/new.py` | Inject `IResultBuilder` + `IAnalyticsPublisher` vào pipeline factory. |
| 19 | `internal/analytics/interface.py` | Thêm `IAnalyticsPublisher` Protocol. |
| 20 | `internal/consumer/registry.py` | Inject `ResultBuilder`, `AnalyticsPublisher`, `KafkaProducer` vào pipeline. |
| 21 | `internal/consumer/type.py` | Thêm `kafka_producer` vào `Dependencies`. |
| 22 | `internal/model/__init__.py` | Export EnrichedOutput types. |
| 23 | `config/config.yaml` | Thêm Kafka producer config section. |
| 24 | `internal/analytics/__init__.py` | Export builder-related types nếu cần. |

### 2.3 Files KHÔNG đổi

- `internal/analytics/delivery/rabbitmq/consumer/` — handler, parser, presenters giữ nguyên
- `internal/analyzed_post/` — repository, usecase giữ nguyên
- AI modules (`sentiment_analysis/`, `keyword_extraction/`, etc.) — giữ nguyên
- `pkg/kafka/` — dùng trực tiếp `KafkaProducer`, `IKafkaProducer` đã có sẵn

---

## 3. CHI TIẾT TỪNG FILE

### 3.1 `internal/model/enriched_output.py` — Enriched Output System Types

**Convention:** System-level types đặt trong `internal/model/` (`convention_python.md` §1). Dùng `dataclass`, không import framework.

```python
"""Enriched Output system-level types.

These types represent the cross-service output contract.
Knowledge Service và các downstream services consume format này qua Kafka.
Payload publish lên Kafka là ARRAY of EnrichedOutput.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# --- Project Block ---

@dataclass
class EnrichedProject:
    """Project context for the enriched output."""
    project_id: str = ""
    entity_type: str = ""
    entity_name: str = ""
    brand: str = ""
    campaign_id: Optional[str] = None


# --- Identity Block ---

@dataclass
class EnrichedAuthor:
    """Author identity."""
    author_id: Optional[str] = None
    display_name: Optional[str] = None
    author_type: str = "user"


@dataclass
class EnrichedIdentity:
    """Source identity and metadata."""
    source_type: str = ""
    source_id: str = ""
    doc_id: str = ""
    doc_type: str = "post"
    url: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[str] = None
    ingested_at: Optional[str] = None
    author: EnrichedAuthor = field(default_factory=EnrichedAuthor)


# --- Content Block ---

@dataclass
class EnrichedContent:
    """Content text blocks."""
    text: str = ""
    clean_text: str = ""
    summary: str = ""


# --- NLP Block ---

@dataclass
class NLPSentiment:
    """Sentiment analysis result."""
    label: str = "NEUTRAL"
    score: float = 0.0
    confidence: str = "LOW"
    explanation: str = ""


@dataclass
class NLPAspect:
    """Single aspect extraction result."""
    aspect: str = ""
    polarity: str = "NEUTRAL"
    confidence: float = 0.0
    evidence: str = ""


@dataclass
class NLPEntity:
    """Named entity recognition result."""
    type: str = ""
    value: str = ""
    confidence: float = 0.0


@dataclass
class EnrichedNLP:
    """NLP analysis results."""
    sentiment: NLPSentiment = field(default_factory=NLPSentiment)
    aspects: list[NLPAspect] = field(default_factory=list)
    entities: list[NLPEntity] = field(default_factory=list)


# --- Business Block ---

@dataclass
class BusinessEngagement:
    """Raw engagement metrics."""
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0


@dataclass
class BusinessImpact:
    """Impact assessment."""
    engagement: BusinessEngagement = field(default_factory=BusinessEngagement)
    impact_score: float = 0.0
    priority: str = "LOW"


@dataclass
class BusinessAlert:
    """Alert triggered by analysis."""
    alert_type: str = ""
    severity: str = "LOW"
    reason: str = ""
    suggested_action: str = ""


@dataclass
class EnrichedBusiness:
    """Business intelligence results."""
    impact: BusinessImpact = field(default_factory=BusinessImpact)
    alerts: list[BusinessAlert] = field(default_factory=list)


# --- RAG Block ---

@dataclass
class RAGQualityGate:
    """Quality gate for RAG indexing."""
    min_length_ok: bool = False
    has_aspect: bool = False
    not_spam: bool = True


@dataclass
class RAGIndex:
    """RAG indexing decision."""
    should_index: bool = False
    quality_gate: RAGQualityGate = field(default_factory=RAGQualityGate)


@dataclass
class RAGCitation:
    """Citation info for RAG responses."""
    source: str = ""
    title: str = ""
    snippet: str = ""
    url: str = ""
    published_at: str = ""


@dataclass
class RAGVectorRef:
    """Vector DB reference."""
    provider: str = "qdrant"
    collection: str = ""
    point_id: str = ""


@dataclass
class EnrichedRAG:
    """RAG-related metadata."""
    index: RAGIndex = field(default_factory=RAGIndex)
    citation: RAGCitation = field(default_factory=RAGCitation)
    vector_ref: RAGVectorRef = field(default_factory=RAGVectorRef)


# --- Provenance Block ---

@dataclass
class ProvenanceStep:
    """Single pipeline step record."""
    step: str = ""
    model: str = ""
    at: str = ""


@dataclass
class EnrichedProvenance:
    """Processing provenance for audit."""
    raw_ref: str = ""
    pipeline: list[ProvenanceStep] = field(default_factory=list)


# --- Root ---

@dataclass
class EnrichedOutput:
    """Root Enriched Output — the canonical output format.

    Kafka payload là ARRAY of EnrichedOutput.
    Knowledge Service và downstream services consume format này.
    """
    enriched_version: str = "1.0"
    event_id: str = ""
    project: EnrichedProject = field(default_factory=EnrichedProject)
    identity: EnrichedIdentity = field(default_factory=EnrichedIdentity)
    content: EnrichedContent = field(default_factory=EnrichedContent)
    nlp: EnrichedNLP = field(default_factory=EnrichedNLP)
    business: EnrichedBusiness = field(default_factory=EnrichedBusiness)
    rag: EnrichedRAG = field(default_factory=EnrichedRAG)
    provenance: EnrichedProvenance = field(default_factory=EnrichedProvenance)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON publish."""
        return _to_dict_recursive(self)


def _to_dict_recursive(obj: Any) -> Any:
    """Recursively convert dataclass to dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict_recursive(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict_recursive(item) for item in obj]
    return obj
```

---

### 3.2 `internal/builder/interface.py` — IResultBuilder Protocol

**Convention:** `convention_python.md` §2 — Protocol + `@runtime_checkable`, prefix `I`.

```python
"""Interface for Result Builder."""

from typing import Protocol, runtime_checkable

from .type import BuildInput, BuildOutput


@runtime_checkable
class IResultBuilder(Protocol):
    """Protocol for building Enriched Output from UAP + AI results.

    Convention: UseCase depends on interface, not implementation.
    """

    def build(self, input_data: BuildInput) -> BuildOutput:
        """Build Enriched Output from UAP record + analytics result.

        Args:
            input_data: BuildInput containing UAP record and analytics result

        Returns:
            BuildOutput containing EnrichedOutput

        Raises:
            ErrBuildFailed: If build fails
        """
        ...
```

---

### 3.3 `internal/builder/type.py` — Builder Types

**Convention:** `convention_python.md` §1 — ALL Input/Output dataclasses trong `type.py`.

```python
"""Data types for Result Builder."""

from dataclasses import dataclass, field
from typing import Optional

from internal.model.uap import UAPRecord
from internal.model.enriched_output import EnrichedOutput
from internal.analytics.type import AnalyticsResult


@dataclass
class BuildInput:
    """Input for ResultBuilder.build().

    Combines UAP record (input context) with analytics result (AI output).
    """
    uap_record: UAPRecord
    analytics_result: AnalyticsResult


@dataclass
class BuildOutput:
    """Output of ResultBuilder.build()."""
    enriched: EnrichedOutput
    success: bool = True
    error_message: Optional[str] = None
```

---

### 3.4 `internal/builder/errors.py` — Builder Errors

```python
"""Module-specific errors for builder domain."""


class ErrBuildFailed(Exception):
    """Raised when building enriched output fails."""
    pass


class ErrMissingUAPRecord(Exception):
    """Raised when UAP record is missing (legacy path — cannot build)."""
    pass


__all__ = [
    "ErrBuildFailed",
    "ErrMissingUAPRecord",
]
```

---

### 3.5 `internal/builder/constant.py` — Builder Constants

```python
"""Constants for Result Builder."""

# Enriched output version
ENRICHED_VERSION = "1.0"

# Citation snippet max length
CITATION_SNIPPET_MAX_LENGTH = 100

# RAG quality gate thresholds
RAG_MIN_TEXT_LENGTH = 10

# Priority thresholds (based on impact_score)
PRIORITY_HIGH_THRESHOLD = 0.7
PRIORITY_MEDIUM_THRESHOLD = 0.4

# Confidence label thresholds
CONFIDENCE_HIGH_THRESHOLD = 0.8
CONFIDENCE_MEDIUM_THRESHOLD = 0.5
```

---

### 3.6 `internal/builder/usecase/new.py` — Factory

**Convention:** `convention_python.md` §4 — `new.py` chỉ là factory.

```python
"""Factory function for creating ResultBuilder."""

from typing import Optional

from pkg.logger.logger import Logger
from ..interface import IResultBuilder
from .build import ResultBuilder


def New(
    logger: Optional[Logger] = None,
) -> IResultBuilder:
    """Create a new ResultBuilder instance.

    Args:
        logger: Logger instance (optional)

    Returns:
        IResultBuilder instance
    """
    return ResultBuilder(logger=logger)


__all__ = ["New"]
```

---

### 3.7 `internal/builder/usecase/build.py` — Core Build Logic

**Convention:** `convention_usecase.md` §2.1 — One file one public method. Framework-agnostic.

```python
"""ResultBuilder — core build logic.

Transform UAP Input + AnalyticsResult → EnrichedOutput.
Convention: UseCase layer — no framework imports.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from pkg.logger.logger import Logger
from internal.model.uap import UAPRecord
from internal.model.enriched_output import (
    EnrichedOutput,
    EnrichedProject,
    EnrichedIdentity,
    EnrichedAuthor,
    EnrichedContent,
    EnrichedNLP,
    NLPSentiment,
    NLPAspect,
    NLPEntity,
    EnrichedBusiness,
    BusinessImpact,
    BusinessEngagement,
    BusinessAlert,
    EnrichedRAG,
    RAGIndex,
    RAGQualityGate,
    RAGCitation,
    RAGVectorRef,
    EnrichedProvenance,
    ProvenanceStep,
)
from internal.analytics.type import AnalyticsResult
from ..type import BuildInput, BuildOutput
from ..errors import ErrBuildFailed
from ..constant import (
    ENRICHED_VERSION,
    CITATION_SNIPPET_MAX_LENGTH,
    RAG_MIN_TEXT_LENGTH,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
)
from .helpers import (
    build_snippet,
    confidence_label,
    determine_priority,
    safe_iso_now,
)


class ResultBuilder:
    """Build Enriched Output from UAP + AI results.

    Convention: UseCase layer — pure logic, no framework imports.
    """

    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger

    def build(self, input_data: BuildInput) -> BuildOutput:
        """Build Enriched Output.

        Args:
            input_data: BuildInput with uap_record + analytics_result

        Returns:
            BuildOutput with EnrichedOutput
        """
        try:
            uap = input_data.uap_record
            result = input_data.analytics_result

            enriched = EnrichedOutput(
                enriched_version=ENRICHED_VERSION,
                event_id=uap.event_id or f"analytics_{uuid.uuid4()}",
                project=self._build_project(uap),
                identity=self._build_identity(uap),
                content=self._build_content(uap, result),
                nlp=self._build_nlp(result),
                business=self._build_business(uap, result),
                rag=self._build_rag(uap, result),
                provenance=self._build_provenance(uap, result),
            )

            return BuildOutput(enriched=enriched, success=True)

        except Exception as exc:
            if self.logger:
                self.logger.error(f"[ResultBuilder] Build failed: {exc}")
            return BuildOutput(
                enriched=EnrichedOutput(),
                success=False,
                error_message=str(exc),
            )

    def _build_project(self, uap: UAPRecord) -> EnrichedProject:
        """Map UAP ingest → project block."""
        return EnrichedProject(
            project_id=uap.ingest.project_id,
            entity_type=uap.ingest.entity.entity_type,
            entity_name=uap.ingest.entity.entity_name,
            brand=uap.ingest.entity.brand,
            campaign_id=uap.context.campaign_id,
        )

    def _build_identity(self, uap: UAPRecord) -> EnrichedIdentity:
        """Map UAP content + ingest → identity block."""
        return EnrichedIdentity(
            source_type=uap.ingest.source.source_type,
            source_id=uap.ingest.source.source_id,
            doc_id=uap.content.doc_id,
            doc_type=uap.content.doc_type,
            url=uap.content.url,
            language=uap.content.language,
            published_at=uap.content.published_at,
            ingested_at=uap.ingest.batch.received_at,
            author=EnrichedAuthor(
                author_id=uap.content.author.author_id,
                display_name=uap.content.author.display_name,
                author_type=uap.content.author.author_type,
            ),
        )

    def _build_content(self, uap: UAPRecord, result: AnalyticsResult) -> EnrichedContent:
        """Map UAP text + AI clean/summary → content block."""
        return EnrichedContent(
            text=uap.content.text,
            clean_text=result.content_text or uap.content.text,
            summary="",  # Phase 4+ — AI summary generation
        )

    def _build_nlp(self, result: AnalyticsResult) -> EnrichedNLP:
        """Map AnalyticsResult AI outputs → NLP block."""
        # Sentiment
        sentiment = NLPSentiment(
            label=result.overall_sentiment,
            score=result.overall_sentiment_score,
            confidence=confidence_label(result.overall_confidence),
            explanation="",  # Phase 4+ — sentiment explanation
        )

        # Aspects — map from aspects_breakdown JSONB
        aspects = []
        if isinstance(result.aspects_breakdown, dict):
            for aspect_data in result.aspects_breakdown.get("aspects", []):
                if isinstance(aspect_data, dict):
                    aspects.append(NLPAspect(
                        aspect=aspect_data.get("aspect", ""),
                        polarity=aspect_data.get("polarity", "NEUTRAL"),
                        confidence=float(aspect_data.get("confidence", 0.0)),
                        evidence=aspect_data.get("evidence", ""),
                    ))

        # Entities — from keywords (basic mapping, Phase 4+ for NER)
        entities = []

        return EnrichedNLP(
            sentiment=sentiment,
            aspects=aspects,
            entities=entities,
        )

    def _build_business(self, uap: UAPRecord, result: AnalyticsResult) -> EnrichedBusiness:
        """Map engagement + impact → business block."""
        engagement = BusinessEngagement(
            like_count=uap.signals.engagement.like_count,
            comment_count=uap.signals.engagement.comment_count,
            share_count=uap.signals.engagement.share_count,
            view_count=uap.signals.engagement.view_count,
        )

        priority = determine_priority(result.impact_score)

        impact = BusinessImpact(
            engagement=engagement,
            impact_score=result.impact_score,
            priority=priority,
        )

        # Alerts — based on risk level (basic, Phase 4+ for full alert engine)
        alerts = []
        if result.risk_level in ("HIGH", "CRITICAL"):
            alerts.append(BusinessAlert(
                alert_type="NEGATIVE_BRAND_SIGNAL",
                severity=result.risk_level,
                reason=f"Post has {result.overall_sentiment} sentiment with {result.risk_level} risk level.",
                suggested_action="Review and monitor related discussions.",
            ))

        return EnrichedBusiness(impact=impact, alerts=alerts)

    def _build_rag(self, uap: UAPRecord, result: AnalyticsResult) -> EnrichedRAG:
        """Build RAG indexing metadata."""
        text = uap.content.text
        has_aspects = bool(result.aspects_breakdown and result.aspects_breakdown.get("aspects"))
        is_not_spam = result.primary_intent not in ("SPAM", "SEEDING")

        quality_gate = RAGQualityGate(
            min_length_ok=len(text) >= RAG_MIN_TEXT_LENGTH,
            has_aspect=has_aspects,
            not_spam=is_not_spam,
        )

        should_index = quality_gate.min_length_ok and quality_gate.not_spam

        citation = RAGCitation(
            source=uap.ingest.source.source_type,
            title=f"{uap.ingest.source.source_type} {uap.content.doc_type.title()}",
            snippet=build_snippet(text, CITATION_SNIPPET_MAX_LENGTH),
            url=uap.content.url or "",
            published_at=uap.content.published_at or "",
        )

        vector_ref = RAGVectorRef(
            provider="qdrant",
            collection=uap.ingest.project_id,
            point_id=uap.event_id,
        )

        return EnrichedRAG(
            index=RAGIndex(should_index=should_index, quality_gate=quality_gate),
            citation=citation,
            vector_ref=vector_ref,
        )

    def _build_provenance(self, uap: UAPRecord, result: AnalyticsResult) -> EnrichedProvenance:
        """Build processing provenance."""
        now = safe_iso_now()
        steps = [
            ProvenanceStep(step="normalize_uap", at=now),
        ]

        # Add AI model steps based on what was executed
        if result.overall_sentiment != "NEUTRAL" or result.overall_confidence > 0:
            steps.append(ProvenanceStep(
                step="sentiment_analysis",
                model=f"phobert-sentiment-v{result.model_version}",
            ))

        if result.aspects_breakdown:
            steps.append(ProvenanceStep(
                step="aspect_extraction",
                model=f"phobert-aspect-v{result.model_version}",
            ))

        if result.keywords:
            steps.append(ProvenanceStep(
                step="keyword_extraction",
                model="spacy-yake",
            ))

        return EnrichedProvenance(
            raw_ref=uap.ingest.trace.raw_ref,
            pipeline=steps,
        )
```

---

### 3.8 `internal/builder/usecase/helpers.py` — Private Helpers

**Convention:** `convention_usecase.md` §2.1 — ALL private helpers in `helpers.py`.

```python
"""Private helpers for ResultBuilder.

Convention: ALL private helper functions in this file.
"""

from datetime import datetime, timezone

from ..constant import (
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
)


def build_snippet(text: str, max_length: int) -> str:
    """Build citation snippet from text."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def confidence_label(score: float) -> str:
    """Convert confidence score to label."""
    if score >= CONFIDENCE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def determine_priority(impact_score: float) -> str:
    """Determine priority from impact score."""
    if impact_score >= PRIORITY_HIGH_THRESHOLD:
        return "HIGH"
    if impact_score >= PRIORITY_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def safe_iso_now() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()
```

---

### 3.9 `internal/builder/__init__.py` — Module Exports

```python
"""Result Builder Domain.

Transforms UAP Input + AI Results → Enriched Output for Kafka publish.
"""

from .interface import IResultBuilder
from .type import BuildInput, BuildOutput
from .errors import ErrBuildFailed, ErrMissingUAPRecord
from .usecase.new import New as NewResultBuilder

__all__ = [
    "IResultBuilder",
    "BuildInput",
    "BuildOutput",
    "ErrBuildFailed",
    "ErrMissingUAPRecord",
    "NewResultBuilder",
]
```

---

### 3.10 `internal/analytics/delivery/kafka/producer/constant.py` — Kafka Constants

```python
"""Constants for analytics Kafka publisher."""

# Output topic
TOPIC_ANALYTICS_OUTPUT = "smap.analytics.output"

# Batch defaults
DEFAULT_BATCH_SIZE = 10
DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
```

---

### 3.11 `internal/analytics/delivery/kafka/producer/type.py` — Kafka Delivery DTOs

**Convention:** `convention_delivery.md` — Delivery DTOs decoupled from domain types.

```python
"""Delivery DTOs for analytics Kafka publisher."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PublishConfig:
    """Configuration for analytics publisher."""
    topic: str = ""
    batch_size: int = 10
    flush_interval_seconds: float = 5.0
    enabled: bool = True
```

---

### 3.12 `internal/analytics/delivery/kafka/producer/publisher.py` — Analytics Publisher

**Convention:** `convention_delivery.md` §5 — Kafka delivery is THIN. Accumulate → serialize → publish. No business logic.

```python
"""Analytics Kafka Publisher.

Convention: Delivery layer — thin.
Accumulate enriched outputs into batch, publish array to Kafka when batch full.
No business logic here.
"""

import json
from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from internal.model.enriched_output import EnrichedOutput
from .type import PublishConfig
from .constant import TOPIC_ANALYTICS_OUTPUT, DEFAULT_BATCH_SIZE


class AnalyticsPublisher:
    """Accumulate and publish enriched outputs to Kafka as batch array.

    Kafka payload format: JSON array of EnrichedOutput dicts.
    """

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
        self._buffer: list[EnrichedOutput] = []

    async def publish(self, enriched: EnrichedOutput) -> None:
        """Add enriched output to buffer. Flush when batch size reached.

        Args:
            enriched: Single EnrichedOutput to accumulate
        """
        if not self._config.enabled:
            return

        self._buffer.append(enriched)

        if len(self._buffer) >= self._config.batch_size:
            await self.flush()

    async def flush(self) -> None:
        """Flush current buffer to Kafka as array.

        Publishes the accumulated batch as a JSON array.
        Clears buffer after successful publish.
        """
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
                    f"[AnalyticsPublisher] Published batch of {len(batch)} "
                    f"to topic={self._config.topic}, key={key}"
                )

        except Exception as exc:
            # Re-add to buffer for retry on next publish
            self._buffer = batch + self._buffer
            if self._logger:
                self._logger.error(
                    f"[AnalyticsPublisher] Failed to publish batch: {exc}"
                )
            raise

    async def close(self) -> None:
        """Flush remaining buffer before shutdown."""
        if self._buffer:
            await self.flush()


__all__ = ["AnalyticsPublisher"]
```

---

### 3.13 `internal/analytics/delivery/kafka/producer/new.py` — Publisher Factory

```python
"""Factory for creating AnalyticsPublisher."""

from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.interface import IKafkaProducer
from .publisher import AnalyticsPublisher
from .type import PublishConfig


def New(
    kafka_producer: IKafkaProducer,
    config: Optional[PublishConfig] = None,
    logger: Optional[Logger] = None,
) -> AnalyticsPublisher:
    """Create a new AnalyticsPublisher instance.

    Args:
        kafka_producer: Kafka producer from pkg/kafka
        config: Publisher config (optional — uses defaults)
        logger: Logger instance (optional)

    Returns:
        AnalyticsPublisher instance
    """
    return AnalyticsPublisher(
        kafka_producer=kafka_producer,
        config=config,
        logger=logger,
    )


__all__ = ["New"]
```

---

### 3.14 `internal/analytics/interface.py` — Thêm IAnalyticsPublisher

**Convention:** `convention_python.md` §2 — Protocol + `@runtime_checkable`.

```python
# === THÊM vào file, sau IAnalyticsPipeline ===

from internal.model.enriched_output import EnrichedOutput


@runtime_checkable
class IAnalyticsPublisher(Protocol):
    """Protocol for publishing enriched analytics output."""

    async def publish(self, enriched: EnrichedOutput) -> None:
        """Publish single enriched output (accumulate into batch)."""
        ...

    async def flush(self) -> None:
        """Flush accumulated batch to Kafka."""
        ...
```

---

### 3.15 `internal/analytics/usecase/usecase.py` — Integrate Builder + Publisher

**Convention:** `convention_usecase.md` — UseCase orchestrates, no framework imports.

**Thay đổi chính:** Sau DB save, nếu có `uap_record` trong Input → build enriched → publish.

```python
# === THÊM imports ===
from internal.builder.interface import IResultBuilder
from internal.builder.type import BuildInput
from internal.analytics.interface import IAnalyticsPublisher

# === SỬA __init__ — thêm dependencies ===
class AnalyticsPipeline(IAnalyticsPipeline):
    def __init__(
        self,
        config: Config,
        analyzed_post_usecase: IAnalyzedPostUseCase,
        logger: Optional[Logger] = None,
        *,
        preprocessor: Optional[Any] = None,
        intent_classifier: Optional[Any] = None,
        keyword_extractor: Optional[Any] = None,
        sentiment_analyzer: Optional[Any] = None,
        impact_calculator: Optional[Any] = None,
        result_builder: Optional[IResultBuilder] = None,      # NEW
        analytics_publisher: Optional[IAnalyticsPublisher] = None,  # NEW
    ):
        # ... existing init ...
        self.result_builder = result_builder
        self.analytics_publisher = analytics_publisher

# === SỬA process() — thêm build + publish sau DB save ===
    async def process(self, input_data: Input) -> Output:
        # ... existing code until after DB save ...

            # Persist result (async)
            await self.analyzed_post_usecase.create(
                CreateAnalyzedPostInput(data=result.to_dict())
            )

            # NEW: Build enriched output + publish to Kafka
            await self._publish_enriched(input_data, result)

            # ... rest of existing code ...

# === THÊM private method ===
    async def _publish_enriched(
        self,
        input_data: Input,
        result: AnalyticsResult,
    ) -> None:
        """Build enriched output and publish to Kafka.

        Only runs if:
        1. result_builder is injected
        2. analytics_publisher is injected
        3. input_data has uap_record (UAP path only — legacy path skips)
        """
        if not self.result_builder or not self.analytics_publisher:
            return
        if not input_data.uap_record:
            return  # Legacy path — no UAP record, skip enriched publish

        try:
            build_input = BuildInput(
                uap_record=input_data.uap_record,
                analytics_result=result,
            )
            build_output = self.result_builder.build(build_input)

            if build_output.success:
                await self.analytics_publisher.publish(build_output.enriched)
            else:
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsPipeline] Build enriched failed: {build_output.error_message}"
                    )

        except Exception as exc:
            # Non-fatal — log but don't fail the pipeline
            if self.logger:
                self.logger.error(
                    f"[AnalyticsPipeline] Publish enriched failed: {exc}"
                )
```

**Lưu ý quan trọng:**

- `_publish_enriched` là **non-fatal** — nếu build hoặc publish fail, pipeline vẫn return success (DB đã save).
- Chỉ chạy khi `uap_record` có giá trị — legacy path (Phase 1 backward compat) tự động skip.
- `result_builder` và `analytics_publisher` là `Optional` — nếu không inject, skip silently.

---

### 3.16 `internal/analytics/usecase/new.py` — Inject Builder + Publisher

```python
# === SỬA factory — thêm params ===

from internal.builder.interface import IResultBuilder
from internal.analytics.interface import IAnalyticsPublisher

def New(
    config: Config,
    analyzed_post_usecase: IAnalyzedPostUseCase,
    logger: Optional[Logger] = None,
    *,
    preprocessor=None,
    intent_classifier=None,
    keyword_extractor=None,
    sentiment_analyzer=None,
    impact_calculator=None,
    result_builder: Optional[IResultBuilder] = None,      # NEW
    analytics_publisher: Optional[IAnalyticsPublisher] = None,  # NEW
) -> AnalyticsPipeline:
    return AnalyticsPipeline(
        config=config,
        analyzed_post_usecase=analyzed_post_usecase,
        logger=logger,
        preprocessor=preprocessor,
        intent_classifier=intent_classifier,
        keyword_extractor=keyword_extractor,
        sentiment_analyzer=sentiment_analyzer,
        impact_calculator=impact_calculator,
        result_builder=result_builder,
        analytics_publisher=analytics_publisher,
    )
```

---

### 3.17 `internal/consumer/type.py` — Thêm Kafka Producer Dependency

```python
# === THÊM import ===
from pkg.kafka.producer import KafkaProducer

# === SỬA Dependencies dataclass — thêm field ===
@dataclass
class Dependencies:
    # ... existing fields ...
    kafka_producer: Optional[KafkaProducer] = None  # NEW: Kafka producer for output
```

---

### 3.18 `internal/consumer/registry.py` — Inject Builder + Publisher

**Thay đổi trong `initialize()`:**

```python
# === THÊM imports ===
from internal.builder import NewResultBuilder
from internal.analytics.delivery.kafka.producer.new import New as NewAnalyticsPublisher
from internal.analytics.delivery.kafka.producer.type import PublishConfig
from internal.analytics.delivery.rabbitmq.consumer.uap_parser import UAPParser

# === THÊM vào initialize(), sau analytics_pipeline init ===

            # Initialize result builder
            result_builder = NewResultBuilder(logger=self.logger)
            self.logger.info("[ConsumerRegistry] Result builder initialized")

            # Initialize analytics publisher (Kafka output)
            analytics_publisher = None
            if self.deps.kafka_producer:
                publish_config = PublishConfig(
                    topic="smap.analytics.output",
                    batch_size=getattr(
                        getattr(self.config, 'kafka', None),
                        'batch_publish_size', 10
                    ),
                    enabled=True,
                )
                analytics_publisher = NewAnalyticsPublisher(
                    kafka_producer=self.deps.kafka_producer,
                    config=publish_config,
                    logger=self.logger,
                )
                self.logger.info("[ConsumerRegistry] Analytics publisher initialized")

# === SỬA NewAnalyticsPipeline call — thêm builder + publisher ===
            analytics_pipeline = NewAnalyticsPipeline(
                config=analytics_config,
                analyzed_post_usecase=analyzed_post_usecase,
                logger=self.logger,
                preprocessor=text_processing,
                intent_classifier=intent_classification,
                keyword_extractor=keyword_extraction,
                sentiment_analyzer=sentiment_analysis,
                impact_calculator=impact_calculation,
                result_builder=result_builder,              # NEW
                analytics_publisher=analytics_publisher,     # NEW
            )

# === SỬA NewAnalyticsHandler call — inject UAPParser ===
            uap_parser = UAPParser()
            analytics_handler = NewAnalyticsHandler(
                pipeline=analytics_pipeline,
                logger=self.logger,
                uap_parser=uap_parser,                      # NEW (Phase 1 wiring)
            )
```

---

### 3.19 `internal/model/__init__.py` — Export EnrichedOutput Types

```python
# === THÊM imports ===
from .enriched_output import (
    EnrichedOutput,
    EnrichedProject,
    EnrichedIdentity,
    EnrichedContent,
    EnrichedNLP,
    EnrichedBusiness,
    EnrichedRAG,
    EnrichedProvenance,
)

# === CẬP NHẬT __all__ — thêm ===
# "EnrichedOutput",
# "EnrichedProject",
# "EnrichedIdentity",
# "EnrichedContent",
# "EnrichedNLP",
# "EnrichedBusiness",
# "EnrichedRAG",
# "EnrichedProvenance",
```

---

### 3.20 `config/config.yaml` — Thêm Kafka Producer Config

```yaml
# === THÊM section mới ===
kafka:
  bootstrap_servers: "172.16.21.206:9092"
  producer:
    acks: "all"
    compression_type: "gzip"
    enable_idempotence: true
    linger_ms: 100
  output:
    topic: "smap.analytics.output"
    batch_publish_size: 10
    enabled: true
```

---

## 4. DATA FLOW (Phase 2)

```
Pipeline.process(Input)
    │
    ├── [existing] Run 5-stage AI pipeline
    ├── [existing] Persist to DB (analyzed_post_usecase.create)
    │
    ├── [NEW] Check: has uap_record? has result_builder? has publisher?
    │   │
    │   ├── NO → skip (legacy path, hoặc dependencies chưa inject)
    │   │
    │   └── YES →
    │       ├── ResultBuilder.build(uap_record, analytics_result)
    │       │   → EnrichedOutput dataclass
    │       │
    │       └── AnalyticsPublisher.publish(enriched)
    │           ├── Accumulate vào buffer
    │           ├── Buffer full (≥ batch_size)?
    │           │   ├── YES → flush()
    │           │   │   → Serialize [enriched_1, enriched_2, ...] as JSON array
    │           │   │   → KafkaProducer.send(topic, value=array_bytes, key=project_id)
    │           │   │   → Knowledge Service consume
    │           │   └── NO → wait for more
    │           └── On shutdown → flush() remaining
```

---

## 5. MIGRATION / TRANSITION STRATEGY

### 5.1 Graceful Degradation

- `result_builder` và `analytics_publisher` là `Optional` — nếu Kafka chưa sẵn sàng, pipeline vẫn chạy bình thường (chỉ save DB).
- `_publish_enriched` là non-fatal — exception chỉ log, không fail pipeline.
- Legacy path (không có `uap_record`) tự động skip enriched publish.

### 5.2 Activation

1. Deploy Phase 2 code với `kafka.output.enabled: false` → pipeline chạy bình thường, không publish
2. Setup Kafka topic `smap.analytics.output` trên cluster
3. Set `kafka.output.enabled: true` → bắt đầu publish
4. Knowledge Service bắt đầu consume
5. Monitor batch size, publish latency, error rate

### 5.3 Batch Flush Strategy

- **Normal:** Flush khi buffer đạt `batch_publish_size` (default 10)
- **Shutdown:** `AnalyticsPublisher.close()` flush remaining buffer
- **Error:** Re-add failed batch vào buffer đầu, retry on next publish
- **Future:** Thêm timer-based flush (flush_interval_seconds) nếu traffic thấp

---

## 6. VERIFICATION & TESTING

### 6.1 Unit Tests

| Test | File | Mô tả |
|------|------|--------|
| `test_build_from_crawl` | `tests/test_builder.py` | Build từ crawl UAP + result → verify all blocks |
| `test_build_from_csv` | `tests/test_builder.py` | Build từ csv UAP + result → verify nullable handling |
| `test_build_project_block` | `tests/test_builder.py` | Verify project mapping: project_id, entity, brand, campaign |
| `test_build_identity_block` | `tests/test_builder.py` | Verify identity mapping: source, doc, author |
| `test_build_nlp_block` | `tests/test_builder.py` | Verify NLP mapping: sentiment, aspects |
| `test_build_rag_block` | `tests/test_builder.py` | Verify RAG: should_index, quality_gate, citation snippet |
| `test_build_provenance` | `tests/test_builder.py` | Verify provenance steps based on result |
| `test_build_error_handling` | `tests/test_builder.py` | Build with invalid input → BuildOutput.success=False |
| `test_publisher_accumulate` | `tests/test_publisher.py` | Publish 5 items (batch_size=10) → no flush |
| `test_publisher_flush_on_batch` | `tests/test_publisher.py` | Publish 10 items → auto flush, verify JSON array |
| `test_publisher_flush_on_close` | `tests/test_publisher.py` | Publish 3 items → close() → flush remaining |
| `test_publisher_disabled` | `tests/test_publisher.py` | enabled=False → no accumulate |
| `test_publisher_error_retry` | `tests/test_publisher.py` | Kafka send fails → buffer re-added |
| `test_pipeline_with_builder` | `tests/test_pipeline.py` | Pipeline process with builder + publisher → verify publish called |
| `test_pipeline_without_builder` | `tests/test_pipeline.py` | Pipeline process without builder → no publish, no error |
| `test_pipeline_legacy_path` | `tests/test_pipeline.py` | Legacy input (no uap_record) → no publish |
| `test_enriched_output_to_dict` | `tests/test_enriched_output.py` | Verify to_dict() serialization matches output_example.json structure |

### 6.2 Integration Test

1. Gửi UAP message → pipeline process → verify Kafka topic nhận JSON array
2. Verify mỗi element trong array match `output_example.json` structure
3. Verify batch size: gửi 25 messages → expect 2 batches (10+10) + 5 remaining on flush
4. Verify Kafka key = `project_id` (partition routing)

### 6.3 Regression Test

1. Legacy Event Envelope → pipeline process → DB save thành công, không publish Kafka
2. UAP message + `kafka.output.enabled: false` → DB save, không publish

---

## 7. DEPENDENCY GRAPH

```
internal/model/enriched_output.py                    ← NEW (no dependencies)
    ↑
internal/builder/constant.py                         ← NEW
internal/builder/errors.py                           ← NEW
internal/builder/type.py                             ← NEW (depends: model.uap, model.enriched_output, analytics.type)
internal/builder/interface.py                        ← NEW (depends: builder.type)
    ↑
internal/builder/usecase/helpers.py                  ← NEW (depends: builder.constant)
internal/builder/usecase/build.py                    ← NEW (depends: model.*, analytics.type, builder.*)
internal/builder/usecase/new.py                      ← NEW (depends: builder.interface, build)
internal/builder/__init__.py                         ← NEW (exports)
    ↑
internal/analytics/delivery/kafka/producer/constant.py  ← NEW
internal/analytics/delivery/kafka/producer/type.py      ← NEW
internal/analytics/delivery/kafka/producer/publisher.py ← NEW (depends: pkg/kafka, model.enriched_output)
internal/analytics/delivery/kafka/producer/new.py       ← NEW (depends: publisher)
    ↑
internal/analytics/interface.py                      ← MODIFIED (add IAnalyticsPublisher)
internal/analytics/usecase/usecase.py                ← MODIFIED (add builder + publisher integration)
internal/analytics/usecase/new.py                    ← MODIFIED (inject builder + publisher)
    ↑
internal/consumer/type.py                            ← MODIFIED (add kafka_producer)
internal/consumer/registry.py                        ← MODIFIED (wire builder + publisher + UAPParser)
    ↑
internal/model/__init__.py                           ← MODIFIED (export EnrichedOutput types)
config/config.yaml                                   ← MODIFIED (add kafka config)
```

**Thứ tự implement khuyến nghị:**

1. `internal/model/enriched_output.py` + `internal/model/__init__.py`
2. `internal/builder/` (toàn bộ module: constant, errors, type, interface, usecase)
3. `internal/analytics/delivery/kafka/producer/` (toàn bộ: constant, type, publisher, new)
4. `internal/analytics/interface.py` (thêm `IAnalyticsPublisher`)
5. `internal/analytics/usecase/usecase.py` + `new.py` (integrate builder + publisher)
6. `config/config.yaml` (thêm kafka section)
7. `internal/consumer/type.py` + `registry.py` (wire everything)
