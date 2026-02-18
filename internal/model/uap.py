"""UAP (Unified Analytics Protocol) system-level types and parser.

These types represent the cross-service wire format.
All services consuming/producing UAP data share these definitions.

Provides:
- UAP dataclasses (UAPRecord, UAPIngest, UAPContent, etc.)
- UAP parser (UAPRecord.parse() classmethod)
- UAP errors (ErrUAPValidation, ErrUAPVersionUnsupported)
- UAP constants (UAP_VERSION_1_0, SUPPORTED_VERSIONS)
"""

from dataclasses import dataclass, field
from typing import Any, Optional


UAP_VERSION_1_0 = "1.0"
SUPPORTED_VERSIONS = {UAP_VERSION_1_0}


class ErrUAPValidation(Exception):
    pass


class ErrUAPVersionUnsupported(Exception):
    pass


@dataclass
class UAPEntity:
    entity_type: str = ""  # product, campaign, service, competitor, topic
    entity_name: str = ""  # VF8, iPhone 15
    brand: str = ""  # VinFast


@dataclass
class UAPSource:
    source_id: str = ""
    source_type: str = ""  # FACEBOOK, TIKTOK, YOUTUBE, FILE_UPLOAD, WEBHOOK
    account_ref: dict[str, Any] = field(default_factory=dict)  # {name, id}


@dataclass
class UAPBatch:
    batch_id: str = ""
    mode: str = ""  # SCHEDULED_CRAWL, MANUAL_UPLOAD, WEBHOOK
    received_at: str = ""  # ISO8601


@dataclass
class UAPTrace:
    raw_ref: str = ""  # minio://raw/...
    mapping_id: str = ""  # mapping rule ID


@dataclass
class UAPIngest:
    project_id: str = ""
    entity: UAPEntity = field(default_factory=UAPEntity)
    source: UAPSource = field(default_factory=UAPSource)
    batch: UAPBatch = field(default_factory=UAPBatch)
    trace: UAPTrace = field(default_factory=UAPTrace)


@dataclass
class UAPAuthor:
    author_id: Optional[str] = None
    display_name: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    followers: int = 0
    is_verified: bool = False
    author_type: str = "user"  # user, page, customer


@dataclass
class UAPParent:
    parent_id: Optional[str] = None
    parent_type: Optional[str] = None


@dataclass
class UAPAttachment:
    type: str = ""  # image, video, link
    url: str = ""
    content: str = ""  # OCR text or caption


@dataclass
class UAPContent:
    doc_id: str = ""
    doc_type: str = "post"  # post, comment, video, news, feedback
    text: str = ""
    url: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[str] = None  # ISO8601
    author: UAPAuthor = field(default_factory=UAPAuthor)
    parent: UAPParent = field(default_factory=UAPParent)
    attachments: list[UAPAttachment] = field(default_factory=list)


@dataclass
class UAPEngagement:
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    save_count: int = 0
    rating: Optional[float] = None


@dataclass
class UAPGeo:
    country: Optional[str] = None
    city: Optional[str] = None


@dataclass
class UAPSignals:
    engagement: UAPEngagement = field(default_factory=UAPEngagement)
    geo: UAPGeo = field(default_factory=UAPGeo)


@dataclass
class UAPContext:
    keywords_matched: list[str] = field(default_factory=list)
    campaign_id: Optional[str] = None


@dataclass
class UAPRecord:
    uap_version: str = ""
    event_id: str = ""
    ingest: UAPIngest = field(default_factory=UAPIngest)
    content: UAPContent = field(default_factory=UAPContent)
    signals: UAPSignals = field(default_factory=UAPSignals)
    context: UAPContext = field(default_factory=UAPContext)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "UAPRecord":
        # Version check
        version = raw.get("uap_version", "")
        if version not in SUPPORTED_VERSIONS:
            raise ErrUAPVersionUnsupported(
                f"unsupported uap_version: '{version}', expected one of {SUPPORTED_VERSIONS}"
            )

        # Required blocks
        ingest_raw = raw.get("ingest")
        content_raw = raw.get("content")
        if not ingest_raw or not isinstance(ingest_raw, dict):
            raise ErrUAPValidation("missing or invalid 'ingest' block")
        if not content_raw or not isinstance(content_raw, dict):
            raise ErrUAPValidation("missing or invalid 'content' block")

        # Parse blocks
        ingest = cls._parse_ingest(ingest_raw)
        content = cls._parse_content(content_raw)
        signals = cls._parse_signals(raw.get("signals", {}))
        context = cls._parse_context(raw.get("context", {}))

        # Required field validation
        if not content.doc_id:
            raise ErrUAPValidation("content.doc_id is required")
        if not ingest.project_id:
            raise ErrUAPValidation("ingest.project_id is required")

        return cls(
            uap_version=version,
            event_id=raw.get("event_id", ""),
            ingest=ingest,
            content=content,
            signals=signals,
            context=context,
            raw=raw.get("raw", {}),
        )

    @staticmethod
    def _parse_ingest(data: dict[str, Any]) -> UAPIngest:
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

    @staticmethod
    def _parse_content(data: dict[str, Any]) -> UAPContent:
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
                followers=author_raw.get("followers", 0),
                is_verified=author_raw.get("is_verified", False),
            ),
            parent=UAPParent(
                parent_id=parent_raw.get("parent_id"),
                parent_type=parent_raw.get("parent_type"),
            ),
            attachments=attachments,
        )

    @staticmethod
    def _parse_signals(data: dict[str, Any]) -> UAPSignals:
        if not data or not isinstance(data, dict):
            return UAPSignals()

        eng_raw = data.get("engagement", {})
        geo_raw = data.get("geo", {})

        return UAPSignals(
            engagement=UAPEngagement(
                like_count=UAPRecord._safe_int(eng_raw.get("like_count")),
                comment_count=UAPRecord._safe_int(eng_raw.get("comment_count")),
                share_count=UAPRecord._safe_int(eng_raw.get("share_count")),
                view_count=UAPRecord._safe_int(eng_raw.get("view_count")),
                save_count=UAPRecord._safe_int(eng_raw.get("save_count")),
                rating=eng_raw.get("rating"),
            ),
            geo=UAPGeo(
                country=geo_raw.get("country"),
                city=geo_raw.get("city"),
            ),
        )

    @staticmethod
    def _parse_context(data: dict[str, Any]) -> UAPContext:
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
