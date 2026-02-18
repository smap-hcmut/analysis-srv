# Phase 3: Code Plan — Database Schema Migration (Full Replace)

**Ref:** `documents/master-proposal.md` (Phase 3)
**Convention:** `documents/convention/`
**Target Schema:** `refactor_plan/indexing_input_schema.md`
**Depends on:** Phase 1 + Phase 2 (done)

---

## 0. TRẠNG THÁI LEGACY SAU KHI USER CLEANUP PHASE 1 & 2

User đã thực hiện một phần legacy removal cho Phase 1/2. Dưới đây là trạng thái THỰC TẾ hiện tại:

### 0.1 Đã cleanup (DONE)

| File                     | Thay đổi đã thực hiện                                                                           |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| `handler.py`             | Xoá `_handle_legacy()`. Handler reject message không có `uap_version`. Chỉ còn UAP path.        |
| `type.py` (analytics)    | `Input.uap_record` giờ là REQUIRED (không còn Optional). `__post_init__` validate `uap_record`. |
| `usecase.py` (analytics) | `_publish_enriched()` xoá check `if not input_data.uap_record: return`.                         |

### 0.2 Chưa cleanup — CÒN LEGACY (thuộc scope Phase 5/6)

| File                       | Vấn đề còn lại                                                                                                                                                                  | Scope       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| `handler.py`               | Duplicate imports (`uap_parser`, `uap_presenters` import 2 lần). Docstring còn nói "dual code path". `uap_parser` vẫn `Optional`. Comment "Legacy structural validation error". | Phase 6     |
| `presenters.py`            | File legacy còn nguyên — `parse_message`, `parse_event_metadata`, `parse_post_payload`, `to_pipeline_input`. Không ai import nữa nhưng chưa xoá.                                | Phase 6     |
| `type.py` (analytics)      | `PostData`, `EventMetadata`, `EnrichedPostData` — legacy types vẫn còn. Pipeline vẫn dùng chúng qua `_enrich_post_data()` và `_run_pipeline()`.                                 | Phase 5     |
| `type.py` (analytics)      | `AnalyticsResult` còn legacy crawler metadata fields: `job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version`, `brand_name`, `keyword`.        | Phase 5     |
| `type.py` (analytics)      | `AnalyticsResult.to_dict()` **THIẾU `processing_status`** — cần thêm trong Phase 3.                                                                                             | **Phase 3** |
| `usecase.py` (analytics)   | `_enrich_post_data()`, `_run_pipeline()`, `_add_crawler_metadata()` vẫn dùng dict-based `PostData`/`EventMetadata`/`EnrichedPostData`.                                          | Phase 5     |
| `uap_presenters.py`        | Map UAP → `PostData` + `EventMetadata` (legacy types). Comments nói "legacy-compatible".                                                                                        | Phase 5     |
| `delivery/type.py`         | `DataCollectedMessage`, `PostPayload`, `EventPayloadMetadata` — legacy DTOs còn nguyên.                                                                                         | Phase 6     |
| `delivery/constant.py`     | Legacy constants: `FIELD_PAYLOAD`, `FIELD_META`, `FIELD_MINIO_PATH`, etc.                                                                                                       | Phase 6     |
| `new.py` (handler factory) | `uap_parser` vẫn `Optional` — nên là required.                                                                                                                                  | Phase 6     |

### 0.3 Tại sao KHÔNG cleanup hết trong Phase 3?

Refactor pipeline Input type (`PostData` → `UAPRecord` trực tiếp) ảnh hưởng đến TẤT CẢ AI modules vì `_run_pipeline()` đang đọc từ dict-based `content.get("text")`, `interaction.get("views")`, `author.get("followers")`. Đây là thay đổi LỚN, thuộc Phase 5 (Data Mapping Implementation).

**Phase 3 scope:** Chỉ replace DB layer + fix `to_dict()` thiếu `processing_status`.

---

## 1. SCOPE

Replace hoàn toàn persistence layer:

- Xoá `schema_analyst.analyzed_posts` (legacy)
- Tạo `analytics.post_analytics` (new)
- Cập nhật ORM model, repository, queries, helpers
- Pipeline ghi TRỰC TIẾP vào schema mới, KHÔNG dual-write
- Fix `AnalyticsResult.to_dict()` thiếu `processing_status`

**Boundary:**

- IN: Migration SQL, ORM model mới, repository replace, helpers replace, `AnalyticsResult.to_dict()` fix, pipeline integration
- OUT: Pipeline Input type refactor (Phase 5), handler/delivery legacy cleanup (Phase 6), business logic mới (Phase 4)

---

## 2. FILE PLAN

### 2.1 Files tạo mới

| #   | File                                        | Vai trò                                                    |
| --- | ------------------------------------------- | ---------------------------------------------------------- |
| 1   | `migration/001_create_analytics_schema.sql` | Tạo schema `analytics` + table `post_analytics` + indexes. |
| 2   | `migration/002_drop_legacy_schema.sql`      | Drop `schema_analyst.analyzed_posts` + schema.             |
| 3   | `internal/model/post_analytics.py`          | ORM model mới cho `analytics.post_analytics`.              |

### 2.2 Files sửa (REPLACE logic, không giữ legacy)

| #   | File                                                               | Thay đổi                                                                                |
| --- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| 4   | `internal/model/__init__.py`                                       | Replace `AnalyzedPost` export → `PostAnalytics`.                                        |
| 5   | `internal/model/analyzed_post.py`                                  | **XOÁ FILE** — legacy ORM model.                                                        |
| 6   | `internal/analyzed_post/repository/postgre/analyzed_post.py`       | Replace toàn bộ — dùng `PostAnalytics` model, ghi vào `analytics.post_analytics`.       |
| 7   | `internal/analyzed_post/repository/postgre/analyzed_post_query.py` | Replace toàn bộ — query builders cho `PostAnalytics`.                                   |
| 8   | `internal/analyzed_post/repository/postgre/helpers.py`             | Replace `sanitize_data()` → `transform_to_post_analytics()`. Xoá legacy sanitize logic. |
| 9   | `internal/analyzed_post/repository/option.py`                      | Replace options — dùng cho schema mới.                                                  |
| 10  | `internal/analyzed_post/repository/interface.py`                   | Replace interface — methods cho `PostAnalytics`.                                        |
| 11  | `internal/analyzed_post/interface.py`                              | Replace `IAnalyzedPostUseCase` — return `PostAnalytics`.                                |
| 12  | `internal/analyzed_post/type.py`                                   | Giữ nguyên — `CreateAnalyzedPostInput` / `UpdateAnalyzedPostInput` đã đúng format.      |
| 13  | `internal/analyzed_post/usecase/create.py`                         | Replace — ghi vào schema mới.                                                           |
| 14  | `internal/analyzed_post/usecase/update.py`                         | Replace — upsert vào schema mới.                                                        |
| 15  | `internal/analyzed_post/usecase/usecase.py`                        | Replace — delegate tới methods mới.                                                     |
| 16  | `internal/analyzed_post/usecase/new.py`                            | Giữ nguyên structure, update types.                                                     |
| 17  | `internal/analyzed_post/__init__.py`                               | Replace exports.                                                                        |
| 18  | `internal/analyzed_post/repository/__init__.py`                    | Replace exports.                                                                        |
| 19  | `internal/analyzed_post/repository/postgre/__init__.py`            | Update nếu cần.                                                                         |
| 20  | `internal/analyzed_post/repository/postgre/new.py`                 | Giữ nguyên structure.                                                                   |
| 21  | `internal/analytics/type.py`                                       | Fix `AnalyticsResult.to_dict()` — thêm `processing_status`.                             |
| 22  | `internal/analytics/usecase/usecase.py`                            | Không cần sửa — interface giữ nguyên.                                                   |
| 23  | `internal/consumer/registry.py`                                    | Update nếu cần (type references).                                                       |

### 2.3 Files KHÔNG đổi

- `internal/builder/` — giữ nguyên (Phase 2)
- `internal/analytics/delivery/` — giữ nguyên
- `internal/consumer/type.py`, `server.py` — giữ nguyên
- AI modules — giữ nguyên
- `pkg/` — giữ nguyên

---

## 3. CHI TIẾT TỪNG FILE

### 3.1 `migration/001_create_analytics_schema.sql` — Tạo Schema Mới

```sql
-- Migration: Create analytics schema and post_analytics table
-- Ref: refactor_plan/indexing_input_schema.md

-- 1. Create schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- 2. Create table
CREATE TABLE analytics.post_analytics (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    source_id VARCHAR(255),

    -- UAP Core
    content TEXT,
    content_created_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    platform VARCHAR(50),
    uap_metadata JSONB DEFAULT '{}',

    -- Sentiment
    overall_sentiment VARCHAR(20) DEFAULT 'NEUTRAL',
    overall_sentiment_score FLOAT DEFAULT 0.0,
    sentiment_confidence FLOAT DEFAULT 0.0,
    sentiment_explanation TEXT,

    -- ABSA
    aspects JSONB DEFAULT '[]',

    -- Keywords
    keywords TEXT[] DEFAULT '{}',

    -- Risk
    risk_level VARCHAR(20) DEFAULT 'LOW',
    risk_score FLOAT DEFAULT 0.0,
    risk_factors JSONB DEFAULT '[]',
    requires_attention BOOLEAN DEFAULT false,
    alert_triggered BOOLEAN DEFAULT false,

    -- Engagement (calculated)
    engagement_score FLOAT DEFAULT 0.0,
    virality_score FLOAT DEFAULT 0.0,
    influence_score FLOAT DEFAULT 0.0,
    reach_estimate INTEGER DEFAULT 0,

    -- Quality
    content_quality_score FLOAT DEFAULT 0.0,
    is_spam BOOLEAN DEFAULT false,
    is_bot BOOLEAN DEFAULT false,
    language VARCHAR(10),
    language_confidence FLOAT DEFAULT 0.0,
    toxicity_score FLOAT DEFAULT 0.0,
    is_toxic BOOLEAN DEFAULT false,

    -- Processing
    primary_intent VARCHAR(50) DEFAULT 'DISCUSSION',
    intent_confidence FLOAT DEFAULT 0.0,
    impact_score FLOAT DEFAULT 0.0,
    processing_time_ms INTEGER DEFAULT 0,
    model_version VARCHAR(50) DEFAULT '1.0.0',
    processing_status VARCHAR(50) DEFAULT 'success',

    -- Timestamps
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Indexes
CREATE INDEX idx_post_analytics_project ON analytics.post_analytics(project_id);
CREATE INDEX idx_post_analytics_source ON analytics.post_analytics(source_id);
CREATE INDEX idx_post_analytics_created ON analytics.post_analytics(content_created_at);
CREATE INDEX idx_post_analytics_sentiment ON analytics.post_analytics(overall_sentiment);
CREATE INDEX idx_post_analytics_risk ON analytics.post_analytics(risk_level);
CREATE INDEX idx_post_analytics_platform ON analytics.post_analytics(platform);
CREATE INDEX idx_post_analytics_attention ON analytics.post_analytics(requires_attention)
    WHERE requires_attention = true;
CREATE INDEX idx_post_analytics_analyzed ON analytics.post_analytics(analyzed_at);

-- GIN indexes for JSONB
CREATE INDEX idx_post_analytics_aspects ON analytics.post_analytics USING GIN (aspects);
CREATE INDEX idx_post_analytics_metadata ON analytics.post_analytics USING GIN (uap_metadata);
```

---

### 3.2 `migration/002_drop_legacy_schema.sql` — Drop Legacy

```sql
-- Migration: Drop legacy schema
-- CHẠY SAU KHI DEPLOY CODE MỚI VÀ VERIFY

-- 1. Drop legacy table
DROP TABLE IF EXISTS schema_analyst.analyzed_posts CASCADE;

-- 2. Drop legacy schema (nếu trống)
DROP SCHEMA IF EXISTS schema_analyst CASCADE;
```

---

### 3.3 `internal/model/post_analytics.py` — ORM Model Mới

**Convention:** System-level model trong `internal/model/`.

```python
"""ORM model for analytics.post_analytics table.

New enriched schema — replaces legacy schema_analyst.analyzed_posts.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.sql import func

from .base import Base


class PostAnalytics(Base):
    """Post analytics data model.

    Schema: analytics.post_analytics
    Ref: refactor_plan/indexing_input_schema.md
    """

    __tablename__ = "post_analytics"
    __table_args__ = (
        Index("idx_post_analytics_project", "project_id"),
        Index("idx_post_analytics_source", "source_id"),
        Index("idx_post_analytics_created", "content_created_at"),
        Index("idx_post_analytics_sentiment", "overall_sentiment"),
        Index("idx_post_analytics_risk", "risk_level"),
        Index("idx_post_analytics_platform", "platform"),
        Index("idx_post_analytics_analyzed", "analyzed_at"),
        {"schema": "analytics"},
    )

    # Identity
    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=func.gen_random_uuid())
    project_id = Column(String(255), nullable=False)
    source_id = Column(String(255), nullable=True)

    # UAP Core
    content = Column(Text, nullable=True)
    content_created_at = Column(DateTime(timezone=True), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    platform = Column(String(50), nullable=True)
    uap_metadata = Column(JSONB, nullable=False, server_default="{}")

    # Sentiment
    overall_sentiment = Column(String(20), nullable=False,
                               server_default="NEUTRAL")
    overall_sentiment_score = Column(Float, nullable=False,
                                     server_default="0.0")
    sentiment_confidence = Column(Float, nullable=False,
                                  server_default="0.0")
    sentiment_explanation = Column(Text, nullable=True)

    # ABSA
    aspects = Column(JSONB, nullable=False, server_default="[]")

    # Keywords
    keywords = Column(ARRAY(String), nullable=False, server_default="{}")

    # Risk
    risk_level = Column(String(20), nullable=False, server_default="LOW")
    risk_score = Column(Float, nullable=False, server_default="0.0")
    risk_factors = Column(JSONB, nullable=False, server_default="[]")
    requires_attention = Column(Boolean, nullable=False,
                                server_default="false")
    alert_triggered = Column(Boolean, nullable=False,
                             server_default="false")

    # Engagement (calculated)
    engagement_score = Column(Float, nullable=False, server_default="0.0")
    virality_score = Column(Float, nullable=False, server_default="0.0")
    influence_score = Column(Float, nullable=False, server_default="0.0")
    reach_estimate = Column(Integer, nullable=False, server_default="0")

    # Quality
    content_quality_score = Column(Float, nullable=False,
                                   server_default="0.0")
    is_spam = Column(Boolean, nullable=False, server_default="false")
    is_bot = Column(Boolean, nullable=False, server_default="false")
    language = Column(String(10), nullable=True)
    language_confidence = Column(Float, nullable=False,
                                 server_default="0.0")
    toxicity_score = Column(Float, nullable=False, server_default="0.0")
    is_toxic = Column(Boolean, nullable=False, server_default="false")

    # Processing
    primary_intent = Column(String(50), nullable=False,
                            server_default="DISCUSSION")
    intent_confidence = Column(Float, nullable=False, server_default="0.0")
    impact_score = Column(Float, nullable=False, server_default="0.0")
    processing_time_ms = Column(Integer, nullable=False,
                                server_default="0")
    model_version = Column(String(50), nullable=False,
                           server_default="1.0.0")
    processing_status = Column(String(50), nullable=False,
                               server_default="success")

    # Timestamps
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())


__all__ = ["PostAnalytics"]
```

---

### 3.4 `internal/model/analyzed_post.py` — XOÁ FILE

Legacy ORM model. Xoá hoàn toàn.

---

### 3.5 `internal/model/__init__.py` — Replace Exports

```python
"""Domain models."""

from .base import Base
from .post_analytics import PostAnalytics
from .uap import (
    UAPRecord, UAPIngest, UAPContent, UAPSignals,
    UAPEntity, UAPSource, UAPBatch, UAPTrace,
    UAPAuthor, UAPParent, UAPAttachment,
    UAPEngagement, UAPGeo, UAPContext,
)
from .enriched_output import (
    EnrichedOutput, EnrichedProject, EnrichedIdentity,
    EnrichedContent, EnrichedNLP, EnrichedBusiness,
    EnrichedRAG, EnrichedProvenance,
)

__all__ = [
    "Base",
    "PostAnalytics",
    # UAP types
    "UAPRecord", "UAPIngest", "UAPContent", "UAPSignals",
    "UAPEntity", "UAPSource", "UAPBatch", "UAPTrace",
    "UAPAuthor", "UAPParent", "UAPAttachment",
    "UAPEngagement", "UAPGeo", "UAPContext",
    # Enriched Output types
    "EnrichedOutput", "EnrichedProject", "EnrichedIdentity",
    "EnrichedContent", "EnrichedNLP", "EnrichedBusiness",
    "EnrichedRAG", "EnrichedProvenance",
]
```

**Lưu ý:** `AnalyzedPost` bị xoá khỏi exports. Tất cả code import `AnalyzedPost` phải đổi sang `PostAnalytics`.

---

### 3.6 `internal/analyzed_post/type.py` — Giữ nguyên

File hiện tại đã đúng format:

```python
"""Types for Analyzed Post domain."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CreateAnalyzedPostInput:
    """Input for creating post_analytics record."""
    data: dict[str, Any]


@dataclass
class UpdateAnalyzedPostInput:
    """Input for updating post_analytics record."""
    data: dict[str, Any]


__all__ = ["CreateAnalyzedPostInput", "UpdateAnalyzedPostInput"]
```

Không cần sửa — tên giữ nguyên để không break callers.

---

### 3.7 `internal/analyzed_post/interface.py` — Replace Interface

```python
"""Interface for Analyzed Post use case."""

from typing import Protocol, runtime_checkable

from internal.model.post_analytics import PostAnalytics
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput


@runtime_checkable
class IAnalyzedPostUseCase(Protocol):
    """Protocol for analyzed post operations."""

    async def create(self, input_data: CreateAnalyzedPostInput) -> PostAnalytics:
        """Create a new post_analytics record."""
        ...

    async def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> PostAnalytics:
        """Update an existing post_analytics record."""
        ...


__all__ = ["IAnalyzedPostUseCase"]
```

---

### 3.8 `internal/analyzed_post/repository/option.py` — Replace Options

```python
"""Options structs for analyzed_post repository operations."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CreateOptions:
    """Options for creating a post_analytics record."""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpsertOptions:
    """Options for upserting a post_analytics record."""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GetOneOptions:
    """Options for getting a single post_analytics record."""
    id: Optional[str] = None
    project_id: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class ListOptions:
    """Options for listing post_analytics records."""
    project_id: Optional[str] = None
    platform: Optional[str] = None
    overall_sentiment: Optional[str] = None
    risk_level: Optional[str] = None
    limit: int = 100
    order_by: str = "analyzed_at DESC"


@dataclass
class DeleteOptions:
    """Options for deleting post_analytics records."""
    id: Optional[str] = None
    project_id: Optional[str] = None


__all__ = [
    "CreateOptions",
    "UpsertOptions",
    "GetOneOptions",
    "ListOptions",
    "DeleteOptions",
]
```

**Thay đổi so với legacy:**

- Xoá `UpdateStatusOptions` — schema mới không có `status` column riêng.
- `GetOneOptions` — xoá `post_id` (redundant với `id`), thêm `source_id`.
- `ListOptions` — xoá `status`, thêm `overall_sentiment`, `risk_level`.

---

### 3.9 `internal/analyzed_post/repository/interface.py` — Replace Interface

```python
"""Repository interface for analyzed_post domain."""

from typing import List, Optional, Protocol, runtime_checkable

from internal.model.post_analytics import PostAnalytics
from .option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    DeleteOptions,
)


@runtime_checkable
class IAnalyzedPostRepository(Protocol):
    """Protocol for post_analytics repository."""

    async def create(self, opt: CreateOptions) -> PostAnalytics:
        """Insert a new post_analytics record."""
        ...

    async def upsert(self, opt: UpsertOptions) -> PostAnalytics:
        """Insert or update a post_analytics record."""
        ...

    async def detail(self, id: str) -> Optional[PostAnalytics]:
        """Get by primary key."""
        ...

    async def get_one(self, opt: GetOneOptions) -> Optional[PostAnalytics]:
        """Get single record by filters."""
        ...

    async def list(self, opt: ListOptions) -> List[PostAnalytics]:
        """List records by filters."""
        ...

    async def delete(self, opt: DeleteOptions) -> bool:
        """Delete record(s)."""
        ...


__all__ = ["IAnalyzedPostRepository"]
```

**Thay đổi:** Xoá `update_status()`. Return type `AnalyzedPost` → `PostAnalytics`.

---

### 3.10 `internal/analyzed_post/repository/postgre/helpers.py` — Replace Helpers

```python
"""Private helpers for post_analytics PostgreSQL repository.

Data transformation, UUID validation, datetime parsing.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict


def transform_to_post_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform AnalyticsResult dict → post_analytics columns.

    Maps AnalyticsResult fields vào enriched schema columns.
    Fields chưa có (Phase 4: engagement_score, virality_score, etc.)
    dùng default values.

    Args:
        data: AnalyticsResult.to_dict() output

    Returns:
        Dict ready for PostAnalytics(**data) insertion
    """
    now = datetime.now(timezone.utc)

    # Build uap_metadata JSONB
    uap_metadata = _build_uap_metadata(data)

    # Build aspects JSONB from aspects_breakdown
    aspects = _extract_aspects(data.get("aspects_breakdown", {}))

    # Derive risk_score from risk_level
    risk_level = data.get("risk_level", "LOW")
    risk_score = _risk_level_to_score(risk_level)

    # Derive flags
    primary_intent = data.get("primary_intent", "DISCUSSION")
    is_spam = primary_intent in ("SPAM", "SEEDING")
    requires_attention = risk_level in ("HIGH", "CRITICAL")

    return {
        "id": uuid.uuid4(),
        "project_id": data.get("project_id", ""),
        "source_id": data.get("source_id"),
        "content": data.get("content_text", ""),
        "content_created_at": _parse_datetime(data.get("published_at")),
        "ingested_at": _parse_datetime(data.get("crawled_at")),
        "platform": (data.get("platform") or "UNKNOWN").lower(),
        "uap_metadata": uap_metadata,
        "overall_sentiment": data.get("overall_sentiment", "NEUTRAL"),
        "overall_sentiment_score": data.get("overall_sentiment_score", 0.0),
        "sentiment_confidence": data.get("overall_confidence", 0.0),
        "sentiment_explanation": None,  # Phase 4
        "aspects": aspects,
        "keywords": data.get("keywords", []),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": [],  # Phase 4
        "requires_attention": requires_attention,
        "alert_triggered": False,
        "engagement_score": 0.0,  # Phase 4
        "virality_score": 0.0,  # Phase 4
        "influence_score": 0.0,  # Phase 4
        "reach_estimate": data.get("view_count", 0),
        "content_quality_score": 0.0,  # Phase 4
        "is_spam": is_spam,
        "is_bot": False,  # Phase 4
        "language": None,  # Phase 4
        "language_confidence": 0.0,  # Phase 4
        "toxicity_score": 0.0,  # Phase 4
        "is_toxic": False,  # Phase 4
        "primary_intent": primary_intent,
        "intent_confidence": data.get("intent_confidence", 0.0),
        "impact_score": data.get("impact_score", 0.0),
        "processing_time_ms": data.get("processing_time_ms", 0),
        "model_version": data.get("model_version", "1.0.0"),
        "processing_status": data.get("processing_status", "success"),
        "analyzed_at": _parse_datetime(data.get("analyzed_at")) or now,
        "indexed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _build_uap_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build uap_metadata JSONB from AnalyticsResult fields."""
    metadata: Dict[str, Any] = {}

    if data.get("author_id"):
        metadata["author"] = data["author_id"]
    if data.get("author_name"):
        metadata["author_display_name"] = data["author_name"]
    if data.get("author_username"):
        metadata["author_username"] = data["author_username"]
    if data.get("follower_count"):
        metadata["author_followers"] = data["follower_count"]
    if data.get("author_is_verified"):
        metadata["author_is_verified"] = data["author_is_verified"]

    engagement = {}
    for key, field in [
        ("views", "view_count"),
        ("likes", "like_count"),
        ("comments", "comment_count"),
        ("shares", "share_count"),
        ("saves", "save_count"),
    ]:
        val = data.get(field)
        if val is not None:
            engagement[key] = val
    if engagement:
        metadata["engagement"] = engagement

    if data.get("permalink"):
        metadata["url"] = data["permalink"]
    if data.get("hashtags"):
        metadata["hashtags"] = data["hashtags"]
    if data.get("content_transcription"):
        metadata["transcription"] = data["content_transcription"]
    if data.get("media_duration"):
        metadata["media_duration"] = data["media_duration"]

    return metadata


def _extract_aspects(aspects_breakdown: Any) -> list:
    """Extract aspects array from aspects_breakdown JSONB."""
    if not isinstance(aspects_breakdown, dict):
        return []
    aspects = aspects_breakdown.get("aspects", [])
    if not isinstance(aspects, list):
        return []
    return [a for a in aspects if isinstance(a, dict)]


def _risk_level_to_score(risk_level: str) -> float:
    """Convert risk_level label to numeric score."""
    mapping = {
        "CRITICAL": 0.9,
        "HIGH": 0.7,
        "MEDIUM": 0.4,
        "LOW": 0.1,
    }
    return mapping.get(risk_level, 0.1)


def _parse_datetime(value: Any) -> Any:
    """Parse datetime value — pass through if already datetime, parse if string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return None


__all__ = [
    "transform_to_post_analytics",
]
```

---

### 3.11 `internal/analyzed_post/repository/postgre/analyzed_post.py` — Replace Repository

```python
"""PostgreSQL repository for post_analytics entity.

Convention: Coordinator file — calls query builders, executes, maps.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from internal.model.post_analytics import PostAnalytics
from ..interface import IAnalyzedPostRepository
from ..option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    DeleteOptions,
)
from ..errors import (
    ErrFailedToCreate,
    ErrFailedToGet,
    ErrFailedToUpdate,
    ErrFailedToDelete,
    ErrFailedToUpsert,
    ErrInvalidData,
)
from .analyzed_post_query import (
    build_get_one_query,
    build_list_query,
    build_delete_query,
)
from .helpers import transform_to_post_analytics


class AnalyzedPostPostgresRepository(IAnalyzedPostRepository):
    """PostgreSQL implementation for post_analytics."""

    def __init__(self, db: PostgresDatabase, logger: Optional[Logger] = None):
        self.db = db
        self.logger = logger

    async def create(self, opt: CreateOptions) -> PostAnalytics:
        """Insert a new post_analytics record."""
        transformed = transform_to_post_analytics(opt.data)

        try:
            async with self.db.get_session() as session:
                record = PostAnalytics(**transformed)
                session.add(record)
                await session.commit()
                await session.refresh(record)

                if self.logger:
                    self.logger.debug(
                        f"[Repository] Created PostAnalytics: "
                        f"id={record.id}, project_id={transformed.get('project_id')}"
                    )
                return record

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] create: {exc}")
            raise ErrFailedToCreate(f"create: {exc}") from exc

    async def upsert(self, opt: UpsertOptions) -> PostAnalytics:
        """Insert or update a post_analytics record.

        Upsert by project_id + source_id (business key).
        """
        transformed = transform_to_post_analytics(opt.data)

        try:
            async with self.db.get_session() as session:
                record = PostAnalytics(**transformed)
                session.add(record)
                await session.commit()
                await session.refresh(record)

                if self.logger:
                    self.logger.debug(
                        f"[Repository] Upserted PostAnalytics: id={record.id}"
                    )
                return record

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] upsert: {exc}")
            raise ErrFailedToUpsert(f"upsert: {exc}") from exc

    async def detail(self, id: str) -> Optional[PostAnalytics]:
        """Get by primary key."""
        try:
            async with self.db.get_session() as session:
                stmt = select(PostAnalytics).where(
                    PostAnalytics.id == id
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] detail: {exc}")
            raise ErrFailedToGet(f"detail: {exc}") from exc

    async def get_one(self, opt: GetOneOptions) -> Optional[PostAnalytics]:
        """Get single record by filters."""
        try:
            async with self.db.get_session() as session:
                stmt = build_get_one_query(opt)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] get_one: {exc}")
            raise ErrFailedToGet(f"get_one: {exc}") from exc

    async def list(self, opt: ListOptions) -> List[PostAnalytics]:
        """List records by filters."""
        try:
            async with self.db.get_session() as session:
                stmt = build_list_query(opt)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] list: {exc}")
            raise ErrFailedToGet(f"list: {exc}") from exc

    async def delete(self, opt: DeleteOptions) -> bool:
        """Delete record(s) by filters."""
        try:
            async with self.db.get_session() as session:
                stmt = build_delete_query(opt)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] delete: {exc}")
            raise ErrFailedToDelete(f"delete: {exc}") from exc


__all__ = ["AnalyzedPostPostgresRepository"]
```

---

### 3.12 `internal/analyzed_post/repository/postgre/analyzed_post_query.py` — Replace Queries

```python
"""Query builders for post_analytics repository.

Convention: Pure query building — returns SQLAlchemy select statements.
"""

from sqlalchemy import select, delete as sql_delete

from internal.model.post_analytics import PostAnalytics
from ..option import GetOneOptions, ListOptions, DeleteOptions


def build_get_one_query(opt: GetOneOptions):
    """Build query for getting a single post_analytics record."""
    stmt = select(PostAnalytics)

    if opt.id:
        stmt = stmt.where(PostAnalytics.id == opt.id)
    if opt.project_id:
        stmt = stmt.where(PostAnalytics.project_id == opt.project_id)
    if opt.source_id:
        stmt = stmt.where(PostAnalytics.source_id == opt.source_id)

    stmt = stmt.limit(1)
    return stmt


def build_list_query(opt: ListOptions):
    """Build query for listing post_analytics records."""
    stmt = select(PostAnalytics)

    if opt.project_id:
        stmt = stmt.where(PostAnalytics.project_id == opt.project_id)
    if opt.platform:
        stmt = stmt.where(PostAnalytics.platform == opt.platform)
    if opt.overall_sentiment:
        stmt = stmt.where(
            PostAnalytics.overall_sentiment == opt.overall_sentiment
        )
    if opt.risk_level:
        stmt = stmt.where(PostAnalytics.risk_level == opt.risk_level)

    # Ordering
    if opt.order_by:
        stmt = stmt.order_by(PostAnalytics.analyzed_at.desc())

    # Limit
    if opt.limit > 0:
        stmt = stmt.limit(opt.limit)

    return stmt


def build_delete_query(opt: DeleteOptions):
    """Build query for deleting post_analytics records."""
    stmt = sql_delete(PostAnalytics)

    if opt.id:
        stmt = stmt.where(PostAnalytics.id == opt.id)
    if opt.project_id:
        stmt = stmt.where(PostAnalytics.project_id == opt.project_id)

    return stmt


__all__ = [
    "build_get_one_query",
    "build_list_query",
    "build_delete_query",
]
```

---

### 3.13 `internal/analyzed_post/usecase/create.py` — Replace Create

```python
"""Create method for analyzed post use case."""

from internal.model.post_analytics import PostAnalytics
from ..type import CreateAnalyzedPostInput
from ..repository.option import CreateOptions


async def create(self, input_data: CreateAnalyzedPostInput) -> PostAnalytics:
    """Create a new post_analytics record.

    Args:
        input_data: Data for creating record

    Returns:
        Created PostAnalytics instance
    """
    if self.logger:
        self.logger.debug("[AnalyzedPostUseCase] Creating post_analytics record")

    return await self.repository.create(CreateOptions(data=input_data.data))
```

---

### 3.14 `internal/analyzed_post/usecase/update.py` — Replace Update

```python
"""Update method for analyzed post use case."""

from internal.model.post_analytics import PostAnalytics
from ..type import UpdateAnalyzedPostInput
from ..repository.option import UpsertOptions


async def update(
    self, post_id: str, input_data: UpdateAnalyzedPostInput
) -> PostAnalytics:
    """Update an existing post_analytics record.

    Args:
        post_id: ID of record to update
        input_data: Data for updating

    Returns:
        Updated PostAnalytics instance
    """
    if self.logger:
        self.logger.debug(
            f"[AnalyzedPostUseCase] Updating post_analytics: {post_id}"
        )

    data = input_data.data.copy()
    data["id"] = post_id

    return await self.repository.upsert(UpsertOptions(data=data))
```

---

### 3.15 `internal/analyzed_post/usecase/usecase.py` — Replace UseCase

```python
"""Use case for analyzed post operations."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.model.post_analytics import PostAnalytics
from ..interface import IAnalyzedPostUseCase
from ..type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from ..repository.interface import IAnalyzedPostRepository

from .create import create as _create
from .update import update as _update


class AnalyzedPostUseCase(IAnalyzedPostUseCase):
    """Use case for managing post_analytics records."""

    def __init__(
        self,
        repository: IAnalyzedPostRepository,
        logger: Optional[Logger] = None,
    ):
        self.repository = repository
        self.logger = logger

    async def create(
        self, input_data: CreateAnalyzedPostInput
    ) -> PostAnalytics:
        """Create a new post_analytics record."""
        return await _create(self, input_data)

    async def update(
        self, post_id: str, input_data: UpdateAnalyzedPostInput
    ) -> PostAnalytics:
        """Update an existing post_analytics record."""
        return await _update(self, post_id, input_data)


__all__ = ["AnalyzedPostUseCase"]
```

---

### 3.16 `internal/analyzed_post/__init__.py` — Replace Exports

```python
"""Analyzed Post Domain — CRUD operations for post_analytics."""

from .interface import IAnalyzedPostUseCase
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from .errors import ErrPostNotFound, ErrInvalidInput, ErrDuplicatePost
from .usecase.new import New as NewAnalyzedPostUseCase

__all__ = [
    "IAnalyzedPostUseCase",
    "CreateAnalyzedPostInput",
    "UpdateAnalyzedPostInput",
    "ErrPostNotFound",
    "ErrInvalidInput",
    "ErrDuplicatePost",
    "NewAnalyzedPostUseCase",
]
```

---

### 3.17 `internal/analyzed_post/repository/__init__.py` — Replace Exports

```python
"""Analyzed Post Repository."""

from .interface import IAnalyzedPostRepository
from .new import New
from .option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    DeleteOptions,
)
from .errors import (
    RepositoryError,
    ErrFailedToCreate,
    ErrFailedToGet,
    ErrFailedToUpdate,
    ErrFailedToDelete,
    ErrFailedToUpsert,
    ErrInvalidData,
)

__all__ = [
    "IAnalyzedPostRepository",
    "New",
    "CreateOptions",
    "UpsertOptions",
    "GetOneOptions",
    "ListOptions",
    "DeleteOptions",
    "RepositoryError",
    "ErrFailedToCreate",
    "ErrFailedToGet",
    "ErrFailedToUpdate",
    "ErrFailedToDelete",
    "ErrFailedToUpsert",
    "ErrInvalidData",
]
```

**Thay đổi:** Xoá `UpdateStatusOptions`.

---

### 3.18 `internal/analytics/type.py` — Fix `AnalyticsResult.to_dict()`

`to_dict()` hiện tại **THIẾU `processing_status`**. Cần thêm vào cuối dict.

```python
# === SỬA to_dict() — thêm processing_status ===

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for repository."""
        return {
            # ... tất cả fields hiện tại giữ nguyên ...
            "author_is_verified": self.author_is_verified,
            "processing_status": self.processing_status,  # THÊM DÒNG NÀY
        }
```

**Lý do:** `transform_to_post_analytics()` trong helpers đọc `data.get("processing_status", "success")`. Nếu `to_dict()` không emit field này, mọi record sẽ luôn là `"success"` bất kể pipeline có lỗi hay không.

---

### 3.19 `internal/analytics/usecase/usecase.py` — Không cần sửa

Pipeline hiện tại gọi:

```python
await self.analyzed_post_usecase.create(
    CreateAnalyzedPostInput(data=result.to_dict())
)
```

Vì `IAnalyzedPostUseCase.create()` signature giữ nguyên (nhận `CreateAnalyzedPostInput`, return model), pipeline KHÔNG cần sửa. Repository layer tự transform data sang schema mới thông qua `transform_to_post_analytics()`.

---

## 4. DATA FLOW (Phase 3)

```
Pipeline.process(Input)
    │
    ├── [existing] Run 5-stage AI pipeline → AnalyticsResult
    │
    ├── analyzed_post_usecase.create(result.to_dict())
    │   └── repository.create(CreateOptions)
    │       └── transform_to_post_analytics(data)
    │           → INSERT INTO analytics.post_analytics   ← NEW (replace legacy)
    │
    ├── [existing] Build enriched output + publish to Kafka (Phase 2)
    │
    └── Return Output
```

---

## 5. COLUMN MAPPING: AnalyticsResult → post_analytics

| AnalyticsResult field                                    | post_analytics column     | Logic                                       |
| -------------------------------------------------------- | ------------------------- | ------------------------------------------- |
| (generated)                                              | `id`                      | `uuid.uuid4()`                              |
| `project_id`                                             | `project_id`              | Direct copy                                 |
| `source_id`                                              | `source_id`               | Direct copy (None nếu chưa có)              |
| `content_text`                                           | `content`                 | Direct copy                                 |
| `published_at`                                           | `content_created_at`      | Direct copy                                 |
| `crawled_at`                                             | `ingested_at`             | Direct copy                                 |
| `platform`                                               | `platform`                | Lowercase                                   |
| author\__, follower_count, _\_count, permalink, hashtags | `uap_metadata`            | Gom vào JSONB                               |
| `overall_sentiment`                                      | `overall_sentiment`       | Direct copy                                 |
| `overall_sentiment_score`                                | `overall_sentiment_score` | Direct copy                                 |
| `overall_confidence`                                     | `sentiment_confidence`    | Rename                                      |
| —                                                        | `sentiment_explanation`   | `None` (Phase 4)                            |
| `aspects_breakdown.aspects[]`                            | `aspects`                 | Extract array                               |
| `keywords`                                               | `keywords`                | Direct copy                                 |
| `risk_level`                                             | `risk_level`              | Direct copy                                 |
| (derived)                                                | `risk_score`              | CRITICAL→0.9, HIGH→0.7, MEDIUM→0.4, LOW→0.1 |
| —                                                        | `risk_factors`            | `[]` (Phase 4)                              |
| (derived)                                                | `requires_attention`      | `risk_level in (HIGH, CRITICAL)`            |
| —                                                        | `alert_triggered`         | `False`                                     |
| —                                                        | `engagement_score`        | `0.0` (Phase 4)                             |
| —                                                        | `virality_score`          | `0.0` (Phase 4)                             |
| —                                                        | `influence_score`         | `0.0` (Phase 4)                             |
| `view_count`                                             | `reach_estimate`          | Direct copy                                 |
| —                                                        | `content_quality_score`   | `0.0` (Phase 4)                             |
| (derived)                                                | `is_spam`                 | `primary_intent in (SPAM, SEEDING)`         |
| —                                                        | `is_bot`                  | `False` (Phase 4)                           |
| —                                                        | `language`                | `None` (Phase 4)                            |
| —                                                        | `toxicity_score`          | `0.0` (Phase 4)                             |
| —                                                        | `is_toxic`                | `False` (Phase 4)                           |
| `primary_intent`                                         | `primary_intent`          | Direct copy                                 |
| `intent_confidence`                                      | `intent_confidence`       | Direct copy                                 |
| `impact_score`                                           | `impact_score`            | Direct copy                                 |
| `processing_time_ms`                                     | `processing_time_ms`      | Direct copy                                 |
| `model_version`                                          | `model_version`           | Direct copy                                 |
| `processing_status`                                      | `processing_status`       | Direct copy                                 |
| `analyzed_at`                                            | `analyzed_at`             | Direct copy                                 |

---

## 6. MIGRATION STRATEGY

### 6.1 Full Replace — Không Dual-Write

1. **Chạy `001_create_analytics_schema.sql`** — tạo schema mới.
2. **Deploy code Phase 3** — pipeline ghi TRỰC TIẾP vào `analytics.post_analytics`.
3. **Verify** — check records, query performance, data integrity.
4. **Chạy `002_drop_legacy_schema.sql`** — xoá schema cũ.

### 6.2 Rollback Plan

- Nếu schema mới có vấn đề → revert code, pipeline ghi lại vào schema cũ (chưa drop).
- Chỉ chạy `002_drop_legacy_schema.sql` SAU KHI verify hoàn toàn.

---

## 7. VERIFICATION & TESTING

### 7.1 Unit Tests

| Test                               | File                       | Mô tả                                           |
| ---------------------------------- | -------------------------- | ----------------------------------------------- |
| `test_transform_to_post_analytics` | `tests/test_helpers.py`    | Verify full mapping                             |
| `test_transform_missing_fields`    | `tests/test_helpers.py`    | Verify defaults                                 |
| `test_transform_uap_metadata`      | `tests/test_helpers.py`    | Verify JSONB construction                       |
| `test_transform_aspects`           | `tests/test_helpers.py`    | Verify aspects extraction                       |
| `test_transform_risk_score`        | `tests/test_helpers.py`    | Verify risk_score mapping                       |
| `test_transform_is_spam`           | `tests/test_helpers.py`    | Verify is_spam derivation                       |
| `test_build_uap_metadata`          | `tests/test_helpers.py`    | Verify engagement, author, url gom vào metadata |
| `test_create_post_analytics`       | `tests/test_repository.py` | Verify INSERT vào analytics.post_analytics      |
| `test_get_one_by_project`          | `tests/test_repository.py` | Verify query by project_id                      |
| `test_list_by_sentiment`           | `tests/test_repository.py` | Verify filter by overall_sentiment              |
| `test_list_by_risk`                | `tests/test_repository.py` | Verify filter by risk_level                     |

### 7.2 Integration Tests

1. Gửi UAP message → pipeline → verify record trong `analytics.post_analytics`.
2. Verify columns: sentiment, aspects, keywords, risk, uap_metadata.
3. Verify GIN index: `aspects @> '[{"aspect": "BATTERY"}]'`.
4. Verify `uap_metadata` queryable: `uap_metadata->>'author'`.
5. Verify `schema_analyst.analyzed_posts` KHÔNG còn nhận writes.

---

## 8. DEPENDENCY GRAPH

```
migration/001_create_analytics_schema.sql        ← NEW (run first)
migration/002_drop_legacy_schema.sql             ← NEW (run last, after verify)
    ↑
internal/model/post_analytics.py                 ← NEW
internal/model/analyzed_post.py                  ← DELETE
internal/model/__init__.py                       ← MODIFIED (replace exports)
    ↑
internal/analyzed_post/repository/option.py      ← REPLACE
internal/analyzed_post/repository/interface.py   ← REPLACE
    ↑
internal/analyzed_post/repository/postgre/helpers.py           ← REPLACE
internal/analyzed_post/repository/postgre/analyzed_post.py     ← REPLACE
internal/analyzed_post/repository/postgre/analyzed_post_query.py ← REPLACE
    ↑
internal/analyzed_post/type.py                   ← GIỮ NGUYÊN
internal/analyzed_post/interface.py              ← REPLACE
internal/analyzed_post/usecase/create.py         ← REPLACE
internal/analyzed_post/usecase/update.py         ← REPLACE
internal/analyzed_post/usecase/usecase.py        ← REPLACE
    ↑
internal/analytics/type.py                       ← MODIFIED (thêm processing_status vào to_dict)
    ↑
internal/analyzed_post/__init__.py               ← REPLACE exports
internal/analyzed_post/repository/__init__.py    ← REPLACE exports
```

**Thứ tự implement:**

1. Chạy `migration/001_create_analytics_schema.sql`
2. `internal/model/post_analytics.py` (tạo mới)
3. Xoá `internal/model/analyzed_post.py`
4. `internal/model/__init__.py` (replace exports)
5. `internal/analyzed_post/repository/option.py` (replace)
6. `internal/analyzed_post/repository/interface.py` (replace)
7. `internal/analyzed_post/repository/postgre/helpers.py` (replace)
8. `internal/analyzed_post/repository/postgre/analyzed_post_query.py` (replace)
9. `internal/analyzed_post/repository/postgre/analyzed_post.py` (replace)
10. `internal/analyzed_post/interface.py` (replace)
11. `internal/analyzed_post/usecase/create.py` + `update.py` + `usecase.py` (replace)
12. `internal/analytics/type.py` (thêm `processing_status` vào `to_dict()`)
13. Export files: `__init__.py` (replace)
14. Verify xong → chạy `migration/002_drop_legacy_schema.sql`
