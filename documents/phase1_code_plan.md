# Phase 1: Code Plan — Input Layer Refactoring (UAP Parser)

**⚠️ IMPLEMENTATION STATUS:**

- ✅ **COMPLETED** - UAP parser fully implemented
- **Actual Consumer**: Kafka (NOT RabbitMQ as in some parts of this plan)
- **Actual Path**: `internal/analytics/delivery/kafka/consumer/` (NOT rabbitmq)
- **Reference**: See `documents/analysis.md` for current implementation status

---

**Ref:** `documents/master-proposal.md` (Phase 1)
**Convention:** `documents/convention/`
**UAP Spec:** `refactor_plan/input-output/input/UAP_INPUT_SCHEMA.md`

---

## 1. SCOPE

Chuyển input layer từ Event Envelope sang UAP v1.0, giữ nguyên pipeline phía sau.

**Boundary:**

- IN: Tất cả code liên quan đến parse, validate, map message đầu vào
- OUT: Pipeline usecase (`usecase.py`), repository, AI modules — chưa đổi logic, chỉ đổi Input type

---

## 2. FILE PLAN

### 2.1 Files tạo mới

| #   | File                                                              | Vai trò (Convention ref)                                                                                                                                                                           |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `internal/model/uap.py`                                           | System-level UAP dataclasses. Đây là wire format chung cross-service, đặt trong `internal/model/` theo convention (`convention_python.md` §1: system types trong model).                           |
| 2   | `internal/analytics/delivery/rabbitmq/consumer/uap_parser.py`     | Parse + validate UAP JSON → `UAPRecord`. Đây là delivery-layer logic (structural validation only, convention `convention_delivery.md` §3.2).                                                       |
| 3   | `internal/analytics/delivery/rabbitmq/consumer/uap_presenters.py` | Mapper: `UAPRecord` → domain `Input`. Tách riêng khỏi legacy `presenters.py` để không break code cũ trong giai đoạn chuyển tiếp (convention `convention_delivery.md` §2: presenters = translator). |

### 2.2 Files sửa

| #   | File                                                       | Thay đổi                                                                                                           |
| --- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 4   | `internal/analytics/type.py`                               | Thêm UAP-aware fields vào `Input`, thêm `UAPInput` dataclass. Giữ `PostData`, `EventMetadata` cho backward compat. |
| 5   | `internal/analytics/delivery/constant.py`                  | Thêm UAP field constants.                                                                                          |
| 6   | `internal/analytics/delivery/type.py`                      | Thêm `UAPMessage` delivery DTO.                                                                                    |
| 7   | `internal/analytics/delivery/rabbitmq/consumer/handler.py` | Thêm UAP code path song song legacy. Switch bằng detect `uap_version` trong message.                               |
| 8   | `internal/analytics/delivery/rabbitmq/consumer/new.py`     | Inject `UAPParser` vào handler.                                                                                    |
| 9   | `internal/analytics/errors.py`                             | Thêm `ErrUAPValidation`, `ErrUAPVersionUnsupported`.                                                               |
| 10  | `internal/analytics/constant.py`                           | Thêm UAP-related constants.                                                                                        |
| 11  | `internal/model/__init__.py`                               | Export `UAPRecord` và related types.                                                                               |

### 2.3 Files KHÔNG đổi

- `internal/analytics/usecase/usecase.py` — nhận `Input` như cũ, chỉ có thêm fields
- `internal/analytics/usecase/new.py` — không đổi signature
- `internal/analytics/interface.py` — `IAnalyticsPipeline.process(Input) -> Output` giữ nguyên
- `internal/analytics/delivery/rabbitmq/consumer/presenters.py` — giữ nguyên legacy path
- Toàn bộ `internal/analyzed_post/`, `internal/consumer/`, AI modules, `pkg/`

---

## 3. CHI TIẾT TỪNG FILE

### 3.1 `internal/model/uap.py` — UAP System Types

**Convention:** System-level types đặt trong `internal/model/` (`convention_python.md` §1). Dùng `dataclass`, không import framework.

```python
"""UAP (Unified Analytics Protocol) system-level types.

These types represent the cross-service wire format.
All services consuming/producing UAP data share these definitions.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class UAPEntity:
    """Target entity being monitored."""
    entity_type: str = ""       # product, campaign, service, competitor, topic
    entity_name: str = ""       # VF8, iPhone 15
    brand: str = ""             # VinFast


@dataclass
class UAPSource:
    """Data source origin."""
    source_id: str = ""
    source_type: str = ""       # FACEBOOK, TIKTOK, YOUTUBE, FILE_UPLOAD, WEBHOOK
    account_ref: dict[str, Any] = field(default_factory=dict)  # {name, id}


@dataclass
class UAPBatch:
    """Batch/ingestion metadata."""
    batch_id: str = ""
    mode: str = ""              # SCHEDULED_CRAWL, MANUAL_UPLOAD, WEBHOOK
    received_at: str = ""       # ISO8601


@dataclass
class UAPTrace:
    """Traceability metadata for debug/audit."""
    raw_ref: str = ""           # minio://raw/...
    mapping_id: str = ""        # mapping rule ID


@dataclass
class UAPIngest:
    """Ingestion context: who owns this data, where it came from."""
    project_id: str = ""
    entity: UAPEntity = field(default_factory=UAPEntity)
    source: UAPSource = field(default_factory=UAPSource)
    batch: UAPBatch = field(default_factory=UAPBatch)
    trace: UAPTrace = field(default_factory=UAPTrace)


@dataclass
class UAPAuthor:
    """Content author profile."""
    author_id: Optional[str] = None
    display_name: Optional[str] = None
    author_type: str = "user"   # user, page, customer


@dataclass
class UAPParent:
    """Parent reference for threaded content (comments)."""
    parent_id: Optional[str] = None
    parent_type: Optional[str] = None


@dataclass
class UAPAttachment:
    """Media attachment."""
    type: str = ""              # image, video, link
    url: str = ""
    content: str = ""           # OCR text or caption


@dataclass
class UAPContent:
    """Core content for AI analysis."""
    doc_id: str = ""
    doc_type: str = "post"      # post, comment, video, news, feedback
    text: str = ""
    url: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[str] = None  # ISO8601
    author: UAPAuthor = field(default_factory=UAPAuthor)
    parent: UAPParent = field(default_factory=UAPParent)
    attachments: list[UAPAttachment] = field(default_factory=list)


@dataclass
class UAPEngagement:
    """Social engagement metrics."""
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    rating: Optional[float] = None


@dataclass
class UAPGeo:
    """Geolocation info."""
    country: Optional[str] = None
    city: Optional[str] = None


@dataclass
class UAPSignals:
    """Numeric signals for scoring and filtering."""
    engagement: UAPEngagement = field(default_factory=UAPEngagement)
    geo: UAPGeo = field(default_factory=UAPGeo)


@dataclass
class UAPContext:
    """Enriched context from ingest layer."""
    keywords_matched: list[str] = field(default_factory=list)
    campaign_id: Optional[str] = None


@dataclass
class UAPRecord:
    """Root UAP record — the canonical input format.

    Every message from Collector MUST conform to this structure.
    """
    uap_version: str = ""
    event_id: str = ""
    ingest: UAPIngest = field(default_factory=UAPIngest)
    content: UAPContent = field(default_factory=UAPContent)
    signals: UAPSignals = field(default_factory=UAPSignals)
    context: UAPContext = field(default_factory=UAPContext)
    raw: dict[str, Any] = field(default_factory=dict)
```

**Export trong `internal/model/__init__.py`:**

```python
from .uap import (
    UAPRecord, UAPIngest, UAPContent, UAPSignals,
    UAPEntity, UAPSource, UAPBatch, UAPTrace,
    UAPAuthor, UAPParent, UAPAttachment,
    UAPEngagement, UAPGeo, UAPContext,
)
```

---

### 3.2 `internal/analytics/delivery/rabbitmq/consumer/uap_parser.py` — UAP Parser

**Convention:** Delivery layer — structural validation only (`convention_delivery.md` §3.2). Không chứa business logic.

```python
"""UAP message parser.

Convention: Delivery layer — structural validation only.
Parse raw JSON → UAPRecord. Reject invalid format.
Business validation belongs in UseCase.
"""

from typing import Any

from internal.model.uap import (
    UAPRecord, UAPIngest, UAPContent, UAPSignals,
    UAPEntity, UAPSource, UAPBatch, UAPTrace,
    UAPAuthor, UAPParent, UAPAttachment,
    UAPEngagement, UAPGeo, UAPContext,
)
from internal.analytics.errors import ErrUAPValidation, ErrUAPVersionUnsupported
from internal.analytics.constant import UAP_VERSION_1_0


class UAPParser:
    """Parse and validate UAP JSON messages.

    Structural validation only:
    - uap_version must be supported
    - Required blocks must exist (ingest, content)
    - Required fields must be non-empty (content.doc_id, ingest.project_id)
    """

    SUPPORTED_VERSIONS = {UAP_VERSION_1_0}

    def parse(self, raw: dict[str, Any]) -> UAPRecord:
        """Parse raw JSON dict into UAPRecord.

        Args:
            raw: Parsed JSON dict from message body

        Returns:
            UAPRecord dataclass

        Raises:
            ErrUAPVersionUnsupported: If uap_version not supported
            ErrUAPValidation: If required fields missing
        """
        # 1. Version check
        version = raw.get("uap_version", "")
        if version not in self.SUPPORTED_VERSIONS:
            raise ErrUAPVersionUnsupported(
                f"unsupported uap_version: '{version}', expected one of {self.SUPPORTED_VERSIONS}"
            )

        # 2. Required blocks
        ingest_raw = raw.get("ingest")
        content_raw = raw.get("content")
        if not ingest_raw or not isinstance(ingest_raw, dict):
            raise ErrUAPValidation("missing or invalid 'ingest' block")
        if not content_raw or not isinstance(content_raw, dict):
            raise ErrUAPValidation("missing or invalid 'content' block")

        # 3. Parse blocks
        ingest = self._parse_ingest(ingest_raw)
        content = self._parse_content(content_raw)
        signals = self._parse_signals(raw.get("signals", {}))
        context = self._parse_context(raw.get("context", {}))

        # 4. Required field validation
        if not content.doc_id:
            raise ErrUAPValidation("content.doc_id is required")
        if not ingest.project_id:
            raise ErrUAPValidation("ingest.project_id is required")

        return UAPRecord(
            uap_version=version,
            event_id=raw.get("event_id", ""),
            ingest=ingest,
            content=content,
            signals=signals,
            context=context,
            raw=raw.get("raw", {}),
        )

    def _parse_ingest(self, data: dict[str, Any]) -> UAPIngest:
        """Parse ingest block."""
        entity_raw = data.get("entity", {})
        source_raw = data.get("source", {})
        batch_raw = data.get("batch", {})
        trace_raw = data.get("trace", {})

        return UAPIngest(
            project_id=data.get("project_id", ""),
            entity=UAPEntity(
                entity_type=entity_raw.get("entity_type", ""),
                entity_name=entity_raw.get("entity_name", ""),
                brand=entity_raw.get("brand", ""),
            ),
            source=UAPSource(
                source_id=source_raw.get("source_id", ""),
                source_type=source_raw.get("source_type", ""),
                account_ref=source_raw.get("account_ref", {}),
            ),
            batch=UAPBatch(
                batch_id=batch_raw.get("batch_id", ""),
                mode=batch_raw.get("mode", ""),
                received_at=batch_raw.get("received_at", ""),
            ),
            trace=UAPTrace(
                raw_ref=trace_raw.get("raw_ref", ""),
                mapping_id=trace_raw.get("mapping_id", ""),
            ),
        )

    def _parse_content(self, data: dict[str, Any]) -> UAPContent:
        """Parse content block."""
        author_raw = data.get("author", {})
        parent_raw = data.get("parent", {})
        attachments_raw = data.get("attachments", [])

        attachments = [
            UAPAttachment(
                type=a.get("type", ""),
                url=a.get("url", ""),
                content=a.get("content", ""),
            )
            for a in attachments_raw
            if isinstance(a, dict)
        ]

        return UAPContent(
            doc_id=data.get("doc_id", ""),
            doc_type=data.get("doc_type", "post"),
            text=data.get("text", ""),
            url=data.get("url"),
            language=data.get("language"),
            published_at=data.get("published_at"),
            author=UAPAuthor(
                author_id=author_raw.get("author_id"),
                display_name=author_raw.get("display_name"),
                author_type=author_raw.get("author_type", "user"),
            ),
            parent=UAPParent(
                parent_id=parent_raw.get("parent_id"),
                parent_type=parent_raw.get("parent_type"),
            ),
            attachments=attachments,
        )

    def _parse_signals(self, data: dict[str, Any]) -> UAPSignals:
        """Parse signals block."""
        if not data or not isinstance(data, dict):
            return UAPSignals()

        eng_raw = data.get("engagement", {})
        geo_raw = data.get("geo", {})

        return UAPSignals(
            engagement=UAPEngagement(
                like_count=self._safe_int(eng_raw.get("like_count")),
                comment_count=self._safe_int(eng_raw.get("comment_count")),
                share_count=self._safe_int(eng_raw.get("share_count")),
                view_count=self._safe_int(eng_raw.get("view_count")),
                rating=eng_raw.get("rating"),
            ),
            geo=UAPGeo(
                country=geo_raw.get("country"),
                city=geo_raw.get("city"),
            ),
        )

    def _parse_context(self, data: dict[str, Any]) -> UAPContext:
        """Parse context block."""
        if not data or not isinstance(data, dict):
            return UAPContext()

        return UAPContext(
            keywords_matched=data.get("keywords_matched", []),
            campaign_id=data.get("campaign_id"),
        )

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
```

---

### 3.3 `internal/analytics/delivery/rabbitmq/consumer/uap_presenters.py` — UAP Presenters

**Convention:** `convention_delivery.md` §2 — Presenters = Translator. Map delivery DTO → domain Input. Không chứa business logic.

**Tách riêng khỏi `presenters.py` (legacy)** để không break code cũ trong giai đoạn dual-path.

```python
"""UAP Presenters — map UAPRecord to domain Input.

Convention: Delivery presenters = translator layer.
- to_uap_pipeline_input(): UAPRecord → domain Input
- No business logic here.
"""

from typing import Optional

from internal.model.uap import UAPRecord
from internal.analytics.type import Input, PostData, EventMetadata


def to_uap_pipeline_input(uap_record: UAPRecord) -> Input:
    """Convert UAPRecord (delivery DTO) → domain Input.

    Convention: Mapper from Delivery DTO → UseCase Input.
    Giữ backward compatibility: map UAP fields vào PostData + EventMetadata
    để pipeline hiện tại consume được mà không cần sửa.

    Args:
        uap_record: Parsed UAP record from UAPParser

    Returns:
        Domain Input for analytics pipeline
    """
    post_data = _build_post_data(uap_record)
    event_metadata = _build_event_metadata(uap_record)
    project_id = uap_record.ingest.project_id or None

    return Input(
        post_data=post_data,
        event_metadata=event_metadata,
        project_id=project_id,
    )


def _build_post_data(uap: UAPRecord) -> PostData:
    """Map UAP content + signals → PostData (legacy-compatible).

    PostData.meta phải có key "id" vì pipeline validate Input.__post_init__
    yêu cầu post_data.meta.get("id") is truthy.
    """
    meta = {
        "id": uap.content.doc_id,
        "doc_type": uap.content.doc_type,
        "platform": uap.ingest.source.source_type.lower() if uap.ingest.source.source_type else "",
        "permalink": uap.content.url or "",
        "published_at": uap.content.published_at,
        "language": uap.content.language,
    }

    content = {
        "text": uap.content.text,
    }

    # Map attachments text vào content nếu có (OCR/caption)
    attachment_texts = [
        att.content for att in uap.content.attachments if att.content
    ]
    if attachment_texts:
        content["attachment_texts"] = attachment_texts

    interaction = {
        "views": uap.signals.engagement.view_count,
        "likes": uap.signals.engagement.like_count,
        "comments_count": uap.signals.engagement.comment_count,
        "shares": uap.signals.engagement.share_count,
        "rating": uap.signals.engagement.rating,
    }

    author = {
        "id": uap.content.author.author_id or "",
        "name": uap.content.author.display_name or "",
        "username": "",
        "avatar_url": "",
        "is_verified": False,
        "followers": 0,
    }

    return PostData(
        meta=meta,
        content=content,
        interaction=interaction,
        author=author,
        comments=[],
    )


def _build_event_metadata(uap: UAPRecord) -> EventMetadata:
    """Map UAP ingest → EventMetadata (legacy-compatible)."""
    return EventMetadata(
        event_id=uap.event_id,
        event_type="uap.collected",
        timestamp=uap.ingest.batch.received_at or "",
        minio_path=uap.ingest.trace.raw_ref or None,
        project_id=uap.ingest.project_id or None,
        job_id=uap.ingest.batch.batch_id or None,
        batch_index=None,
        platform=uap.ingest.source.source_type or None,
        task_type=uap.ingest.batch.mode or None,
        brand_name=uap.ingest.entity.brand or None,
        keyword=None,
    )


__all__ = ["to_uap_pipeline_input"]
```

**Giải thích thiết kế:**

- Map UAP → `PostData` + `EventMetadata` (legacy types) để pipeline `usecase.py` consume mà **không cần sửa** trong Phase 1.
- `PostData.meta["id"]` = `content.doc_id` — bắt buộc vì `Input.__post_init__` validate field này.
- `interaction` map engagement metrics vào đúng key names mà `_run_pipeline()` đang dùng (`views`, `likes`, `comments_count`, `shares`).
- Khi Phase 2+ refactor pipeline Input type, presenters này sẽ được cập nhật tương ứng.

---

### 3.4 `internal/analytics/type.py` — Cập nhật Domain Types

**Convention:** `convention_python.md` §1 — ALL Input/Output dataclasses trong `type.py`.

**Thay đổi:** Thêm `uap_record` field vào `Input` để handler có thể truyền raw UAPRecord xuống pipeline cho các phase sau sử dụng. Giữ nguyên `PostData`, `EventMetadata` cho backward compat.

```python
# === THÊM import ở đầu file ===
from internal.model.uap import UAPRecord

# === SỬA dataclass Input — thêm field uap_record ===
@dataclass
class Input:
    """Input structure for analytics pipeline."""

    post_data: PostData
    event_metadata: Optional[EventMetadata] = None
    project_id: Optional[str] = None
    uap_record: Optional[UAPRecord] = None  # NEW: Raw UAP record (Phase 1+)

    def __post_init__(self):
        if not self.post_data:
            raise ValueError("post_data is required")
        if not self.post_data.meta.get("id"):
            raise ValueError("post_data.meta.id is required")
```

**Lưu ý:**

- `uap_record` là `Optional` — legacy path truyền `None`, UAP path truyền record đầy đủ.
- Pipeline `usecase.py` hiện tại KHÔNG đọc `uap_record` — field này dành cho Phase 2+ (ResultBuilder cần UAP metadata để build Enriched Output).
- Không thêm type mới nào khác trong Phase 1. `PostData`, `EventMetadata`, `AnalyticsResult`, `Output` giữ nguyên.

**Cập nhật `__all__`:**

```python
# Không cần sửa __all__ — UAPRecord import từ internal.model, không export lại từ đây.
```

---

### 3.5 `internal/analytics/delivery/constant.py` — Thêm UAP Field Constants

**Convention:** `convention_python.md` §1 — Constants trong `constant.py`.

```python
# === THÊM vào cuối file ===

# UAP message fields
FIELD_UAP_VERSION = "uap_version"
FIELD_INGEST = "ingest"
FIELD_SIGNALS = "signals"
FIELD_CONTEXT = "context"
FIELD_RAW = "raw"
FIELD_DOC_ID = "doc_id"

# UAP ingest sub-fields
FIELD_ENTITY = "entity"
FIELD_SOURCE = "source"
FIELD_BATCH = "batch"
FIELD_TRACE = "trace"
```

**Lưu ý:** Các constants này được `UAPParser` sử dụng gián tiếp (parser dùng string keys trực tiếp vì parse logic đã rõ ràng). Constants chủ yếu phục vụ handler khi detect UAP message và cho các module khác reference.

---

### 3.6 `internal/analytics/delivery/type.py` — Thêm UAPMessage DTO

**Convention:** `convention_delivery.md` — Delivery DTOs decoupled from domain types.

```python
# === THÊM vào cuối file, trước __all__ ===

@dataclass
class UAPMessage:
    """DTO for incoming UAP message from RabbitMQ.

    Wire format — decoupled from domain types.
    Chỉ giữ raw dict để UAPParser xử lý chi tiết.
    """

    uap_version: str = ""
    event_id: str = ""
    raw_body: dict[str, Any] = field(default_factory=dict)


# === CẬP NHẬT __all__ ===
__all__ = [
    "DataCollectedMessage",
    "PostPayload",
    "EventPayloadMetadata",
    "UAPMessage",
]
```

---

### 3.7 `internal/analytics/delivery/rabbitmq/consumer/handler.py` — Dual Code Path

**Convention:** `convention_delivery.md` §3.1 — Handler is THIN. Detect message type → route to correct path.

**Thay đổi chính:**

1. Import `UAPParser` và `to_uap_pipeline_input`
2. Nhận `UAPParser` qua constructor (DI)
3. Trong `handle_message()`: detect `uap_version` key → UAP path vs legacy path
4. Legacy path giữ nguyên 100%

```python
"""Analytics message handler for RabbitMQ consumer.

Convention: Delivery handler is THIN.
Dual code path: UAP (new) vs Event Envelope (legacy).
Detect by presence of 'uap_version' key in message body.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional, TYPE_CHECKING

try:
    from aio_pika import IncomingMessage  # type: ignore

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    if TYPE_CHECKING:
        from aio_pika import IncomingMessage  # type: ignore
    else:
        IncomingMessage = Any

from pkg.logger.logger import Logger
from internal.analytics.interface import IAnalyticsPipeline
from internal.analytics.delivery.constant import (
    FIELD_PAYLOAD,
    FIELD_META,
    FIELD_MINIO_PATH,
    FIELD_UAP_VERSION,
)
from internal.analytics.errors import ErrUAPValidation, ErrUAPVersionUnsupported
from .presenters import (
    parse_message,
    parse_event_metadata,
    parse_post_payload,
    to_pipeline_input,
)
from .uap_parser import UAPParser
from .uap_presenters import to_uap_pipeline_input


class AnalyticsHandler:
    """Handler for processing analytics messages from RabbitMQ.

    Supports dual code path:
    - UAP path: message has 'uap_version' key → UAPParser → uap_presenters
    - Legacy path: Event Envelope → presenters (unchanged)
    """

    def __init__(
        self,
        pipeline: IAnalyticsPipeline,
        logger: Optional[Logger] = None,
        uap_parser: Optional[UAPParser] = None,
    ):
        """Initialize analytics handler.

        Args:
            pipeline: Analytics pipeline instance
            logger: Logger instance (optional)
            uap_parser: UAP parser instance (optional — None disables UAP path)
        """
        self.pipeline = pipeline
        self.logger = logger
        self.uap_parser = uap_parser

    async def handle(self, message: IncomingMessage) -> None:
        """Handle incoming message (called by consumer server)."""
        await self.handle_message(message)

    async def handle_message(self, message: IncomingMessage) -> None:
        """Handle incoming message — route to UAP or legacy path.

        Flow:
        1. Parse JSON
        2. Detect: has 'uap_version'? → UAP path : Legacy path
        3. Parse → Validate → Convert → UseCase → Log
        """
        async with message.process():
            start_time = time.perf_counter()
            event_id = "unknown"

            try:
                # 1. Parse message body
                body = message.body.decode("utf-8")
                envelope = json.loads(body)

                # 2. Route: UAP or Legacy
                if FIELD_UAP_VERSION in envelope and self.uap_parser is not None:
                    pipeline_input = self._handle_uap(envelope)
                    event_id = envelope.get("event_id", "unknown")
                else:
                    pipeline_input = self._handle_legacy(envelope)
                    event_id = envelope.get("event_id", "unknown")

                if self.logger:
                    self.logger.debug(
                        f"[AnalyticsHandler] Received message: event_id={event_id}"
                    )

                # 3. Call UseCase
                output = await self.pipeline.process(pipeline_input)

                # 4. Log result
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                if self.logger:
                    self.logger.info(
                        f"[AnalyticsHandler] Message processed: event_id={event_id}, "
                        f"status={output.processing_status}, elapsed_ms={elapsed_ms}"
                    )

            except json.JSONDecodeError as exc:
                # Poison message — ACK (discard)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Invalid JSON: event_id={event_id}, error={exc}"
                    )
                raise

            except (ErrUAPValidation, ErrUAPVersionUnsupported) as exc:
                # UAP structural validation error — ACK (discard)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] UAP validation error: event_id={event_id}, error={exc}"
                    )
                raise

            except ValueError as exc:
                # Legacy structural validation error — ACK (discard)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Validation error: event_id={event_id}, error={exc}"
                    )
                raise

            except Exception as exc:
                # Business/transient error — NACK (retry)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Processing error: event_id={event_id}, error={exc}"
                    )
                raise

    def _handle_uap(self, envelope: dict[str, Any]):
        """UAP code path: parse → validate → convert to domain Input.

        Args:
            envelope: Raw parsed JSON with uap_version key

        Returns:
            Domain Input for pipeline

        Raises:
            ErrUAPValidation: If UAP format invalid
            ErrUAPVersionUnsupported: If version not supported
        """
        uap_record = self.uap_parser.parse(envelope)
        return to_uap_pipeline_input(uap_record)

    def _handle_legacy(self, envelope: dict[str, Any]):
        """Legacy code path: Event Envelope → presenters → domain Input.

        Giữ nguyên 100% logic cũ.

        Args:
            envelope: Raw parsed JSON (Event Envelope format)

        Returns:
            Domain Input for pipeline

        Raises:
            ValueError: If format invalid
        """
        # Validate format (structural only)
        if not self._validate_format(envelope):
            raise ValueError("Invalid event format: missing required fields")

        msg_dto = parse_message(envelope)
        post_dto = parse_post_payload(msg_dto)
        meta_dto = parse_event_metadata(msg_dto)
        return to_pipeline_input(msg_dto, post_dto, meta_dto)

    def _validate_format(self, envelope: dict[str, Any]) -> bool:
        """Validate legacy event format (structural only)."""
        if FIELD_PAYLOAD not in envelope:
            return False

        payload = envelope.get(FIELD_PAYLOAD, {})
        has_minio_path = FIELD_MINIO_PATH in payload
        has_inline_data = FIELD_META in payload

        return has_minio_path or has_inline_data


__all__ = ["AnalyticsHandler"]
```

**Giải thích thiết kế:**

- Detect bằng `FIELD_UAP_VERSION in envelope` — đơn giản, rõ ràng, không cần config flag.
- `uap_parser` là `Optional` — nếu `None`, mọi message đều đi legacy path (safe fallback).
- `_handle_uap()` và `_handle_legacy()` tách riêng, mỗi method một job.
- Legacy path giữ nguyên 100% logic hiện tại, chỉ extract ra method riêng.
- Error handling: UAP errors (`ErrUAPValidation`, `ErrUAPVersionUnsupported`) → ACK (discard, giống `ValueError` của legacy).

---

### 3.8 `internal/analytics/delivery/rabbitmq/consumer/new.py` — Inject UAPParser

**Convention:** `convention_python.md` §4.7 — `new.py` chỉ là factory.

```python
"""Factory function for creating analytics handler."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.analytics.interface import IAnalyticsPipeline
from .uap_parser import UAPParser
from .handler import AnalyticsHandler


def New(
    pipeline: IAnalyticsPipeline,
    logger: Optional[Logger] = None,
    uap_parser: Optional[UAPParser] = None,
) -> AnalyticsHandler:
    """Create a new analytics handler instance.

    Args:
        pipeline: Analytics pipeline instance
        logger: Logger instance (optional)
        uap_parser: UAP parser instance (optional — None disables UAP path)

    Returns:
        AnalyticsHandler instance

    Raises:
        ValueError: If pipeline is invalid
    """
    if pipeline is None:
        raise ValueError("pipeline cannot be None")

    return AnalyticsHandler(
        pipeline=pipeline,
        logger=logger,
        uap_parser=uap_parser,
    )


__all__ = ["New"]
```

**Thay đổi so với hiện tại:**

- Thêm param `uap_parser: Optional[UAPParser] = None`
- Pass `uap_parser` vào `AnalyticsHandler` constructor
- Caller (registry) quyết định có inject `UAPParser()` hay không

---

### 3.9 `internal/analytics/errors.py` — Thêm UAP Errors

**Convention:** `convention_python.md` §2 — Prefix `Err`, mỗi layer có errors riêng.

```python
# === THÊM vào cuối file, trước __all__ ===

class ErrUAPValidation(Exception):
    """Raised when UAP message fails structural validation.

    Examples: missing 'ingest' block, empty 'content.doc_id'.
    """
    pass


class ErrUAPVersionUnsupported(Exception):
    """Raised when uap_version is not in supported set.

    Example: uap_version="2.0" but parser only supports {"1.0"}.
    """
    pass


# === CẬP NHẬT __all__ ===
__all__ = [
    "ErrPipelineProcessing",
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
    "ErrPersistenceFailed",
    "ErrUAPValidation",
    "ErrUAPVersionUnsupported",
]
```

---

### 3.10 `internal/analytics/constant.py` — Thêm UAP Constants

**Convention:** `convention_python.md` §1 — Constants trong `constant.py`.

```python
# === THÊM vào cuối file, trước __all__ ===

# UAP version constants
UAP_VERSION_1_0 = "1.0"

# UAP event type (dùng trong EventMetadata.event_type cho UAP path)
UAP_EVENT_TYPE = "uap.collected"


# === CẬP NHẬT __all__ — thêm ===
# "UAP_VERSION_1_0",
# "UAP_EVENT_TYPE",
```

---

### 3.11 `internal/model/__init__.py` — Export UAP Types

**Convention:** `convention_python.md` §1 — `__init__.py` exports.

```python
"""Domain models."""

from .base import Base
from .analyzed_post import AnalyzedPost
from .uap import (
    UAPRecord,
    UAPIngest,
    UAPContent,
    UAPSignals,
    UAPEntity,
    UAPSource,
    UAPBatch,
    UAPTrace,
    UAPAuthor,
    UAPParent,
    UAPAttachment,
    UAPEngagement,
    UAPGeo,
    UAPContext,
)

__all__ = [
    "Base",
    "AnalyzedPost",
    "UAPRecord",
    "UAPIngest",
    "UAPContent",
    "UAPSignals",
    "UAPEntity",
    "UAPSource",
    "UAPBatch",
    "UAPTrace",
    "UAPAuthor",
    "UAPParent",
    "UAPAttachment",
    "UAPEngagement",
    "UAPGeo",
    "UAPContext",
]
```

---

## 4. MIGRATION / TRANSITION STRATEGY

### 4.1 Dual-Path Approach

Phase 1 chạy **song song** hai code path trong cùng một handler:

```
Message arrives
    │
    ├── has "uap_version" key? ──YES──→ UAPParser → uap_presenters → Input → Pipeline
    │
    └── NO ──→ Legacy presenters → Input → Pipeline (unchanged)
```

**Ưu điểm:**

- Zero downtime — deploy mà không cần Collector chuyển format cùng lúc
- Rollback dễ — nếu UAP path lỗi, chỉ cần không inject `UAPParser` (pass `None`)
- Test riêng từng path — UAP path test với example JSON, legacy path test regression

### 4.2 Activation Strategy

1. **Deploy Phase 1 code** — `UAPParser` injected nhưng chưa có message UAP nào
2. **Collector bắt đầu publish UAP** — messages mới đi UAP path, messages cũ đi legacy path
3. **Monitor** — log, metrics, error rate cho cả hai path
4. **Collector chuyển hoàn toàn sang UAP** — legacy path idle
5. **Phase 6 (Legacy Cleanup)** — remove legacy path code

### 4.3 Config Flag (Optional)

Nếu cần disable UAP path mà không cần redeploy:

```yaml
# config/config.yaml
analytics:
  uap_enabled: true # false → handler không inject UAPParser
```

Registry đọc flag này khi tạo handler:

```python
# Trong registry/DI code
uap_parser = UAPParser() if config.analytics.uap_enabled else None
handler = handler_new.New(pipeline=pipeline, logger=logger, uap_parser=uap_parser)
```

---

## 5. VERIFICATION & TESTING

### 5.1 Unit Tests cần viết

| Test                                  | File                           | Mô tả                                                                                            |
| ------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------ |
| `test_uap_parser_valid_crawl`         | `tests/test_uap_parser.py`     | Parse `example_input_crawl.json` → UAPRecord, verify tất cả fields                               |
| `test_uap_parser_valid_csv`           | `tests/test_uap_parser.py`     | Parse `example_input_csv.json` → UAPRecord, verify nullable fields                               |
| `test_uap_parser_missing_version`     | `tests/test_uap_parser.py`     | Raise `ErrUAPVersionUnsupported`                                                                 |
| `test_uap_parser_unsupported_version` | `tests/test_uap_parser.py`     | `uap_version="2.0"` → Raise `ErrUAPVersionUnsupported`                                           |
| `test_uap_parser_missing_ingest`      | `tests/test_uap_parser.py`     | Raise `ErrUAPValidation`                                                                         |
| `test_uap_parser_missing_content`     | `tests/test_uap_parser.py`     | Raise `ErrUAPValidation`                                                                         |
| `test_uap_parser_missing_doc_id`      | `tests/test_uap_parser.py`     | Raise `ErrUAPValidation`                                                                         |
| `test_uap_parser_missing_project_id`  | `tests/test_uap_parser.py`     | Raise `ErrUAPValidation`                                                                         |
| `test_uap_presenters_crawl`           | `tests/test_uap_presenters.py` | `to_uap_pipeline_input(crawl_record)` → verify `Input.post_data.meta["id"]`, interaction metrics |
| `test_uap_presenters_csv`             | `tests/test_uap_presenters.py` | `to_uap_pipeline_input(csv_record)` → verify nullable handling                                   |
| `test_handler_uap_path`               | `tests/test_handler.py`        | Message with `uap_version` → goes through UAP path                                               |
| `test_handler_legacy_path`            | `tests/test_handler.py`        | Message without `uap_version` → goes through legacy path                                         |
| `test_handler_uap_disabled`           | `tests/test_handler.py`        | `uap_parser=None` + message with `uap_version` → falls to legacy path                            |

### 5.2 Integration Test

1. Gửi `example_input_crawl.json` vào RabbitMQ queue `smap.collector.output`
2. Verify handler nhận, parse qua UAP path, pipeline process thành công
3. Verify DB record được tạo trong `schema_analyst.analyzed_posts` (schema cũ — Phase 1 chưa đổi DB)
4. Verify log output có `event_id` từ UAP message

### 5.3 Regression Test

1. Gửi legacy Event Envelope message (format cũ)
2. Verify handler nhận, parse qua legacy path, pipeline process thành công
3. Verify kết quả giống hệt trước khi deploy Phase 1

---

## 6. DEPENDENCY GRAPH

```
internal/model/uap.py                          ← NEW (no dependencies)
    ↑
internal/analytics/constant.py                  ← MODIFIED (add UAP_VERSION_1_0)
internal/analytics/errors.py                    ← MODIFIED (add ErrUAPValidation, ErrUAPVersionUnsupported)
    ↑
internal/analytics/delivery/constant.py         ← MODIFIED (add FIELD_UAP_VERSION, etc.)
internal/analytics/delivery/type.py             ← MODIFIED (add UAPMessage)
    ↑
internal/analytics/delivery/rabbitmq/consumer/uap_parser.py      ← NEW (depends: model.uap, errors, constant)
    ↑
internal/analytics/type.py                      ← MODIFIED (add uap_record field to Input)
    ↑
internal/analytics/delivery/rabbitmq/consumer/uap_presenters.py  ← NEW (depends: model.uap, type)
    ↑
internal/analytics/delivery/rabbitmq/consumer/handler.py         ← MODIFIED (depends: uap_parser, uap_presenters)
    ↑
internal/analytics/delivery/rabbitmq/consumer/new.py             ← MODIFIED (inject UAPParser)
    ↑
internal/model/__init__.py                      ← MODIFIED (export UAP types)
```

**Thứ tự implement khuyến nghị:**

1. `internal/model/uap.py` + `internal/model/__init__.py`
2. `internal/analytics/errors.py` + `internal/analytics/constant.py`
3. `internal/analytics/delivery/constant.py` + `internal/analytics/delivery/type.py`
4. `internal/analytics/delivery/rabbitmq/consumer/uap_parser.py`
5. `internal/analytics/type.py`
6. `internal/analytics/delivery/rabbitmq/consumer/uap_presenters.py`
7. `internal/analytics/delivery/rabbitmq/consumer/handler.py`
8. `internal/analytics/delivery/rabbitmq/consumer/new.py`
