"""UAP (Unified Analytics Protocol) system-level types and parser.

These types represent the cross-service wire format.
All services consuming/producing UAP data share these definitions.

Provides:
- UAP dataclasses (UAPRecord, UAPIngest, UAPContent, etc.)
- ingest-srv flat wire-format parser (UAPRecord.from_ingest_record())
- UAP validation error
"""

from dataclasses import dataclass, field
from typing import Any, Optional


class ErrUAPValidation(Exception):
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
    domain_type_code: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_ingest_record(cls, raw: dict[str, Any]) -> "UAPRecord":
        """Parse ingest-srv flat wire format into a UAPRecord.

        ingest-srv emits a flat structure (no uap_version, no ingest/signals/context blocks).
        This classmethod maps each ingest-srv field to the corresponding UAPRecord field.

        Required fields (raises ErrUAPValidation if absent/empty):
            identity.project_id
            identity.uap_id

        Rich metadata (domain_type_code, hierarchy, platform_meta) is stored in .raw
        so no information is lost downstream.
        """
        identity = raw.get("identity") or {}
        content_raw = raw.get("content") or {}
        author_raw = raw.get("author") or {}
        engagement_raw = raw.get("engagement") or {}
        temporal_raw = raw.get("temporal") or {}
        hierarchy_raw = raw.get("hierarchy") or {}
        media_raw = raw.get("media") or []

        # --- Required field validation ---
        project_id = identity.get("project_id", "")
        if not project_id:
            raise ErrUAPValidation("identity.project_id is required")

        uap_id = identity.get("uap_id", "")
        if not uap_id:
            raise ErrUAPValidation("identity.uap_id is required")

        # --- Attachments (media[] → content.attachments[]) ---
        attachments = [
            UAPAttachment(
                type=m.get("type", ""),
                url=m.get("url", "") or m.get("download_url", ""),
                content="",
            )
            for m in media_raw
            if isinstance(m, dict)
        ]

        # --- Keywords: crawl_keyword (str) → keywords_matched ([str]) ---
        crawl_keyword = raw.get("crawl_keyword", "")
        keywords_matched = [crawl_keyword] if crawl_keyword else []

        # --- domain_type_code ---
        domain_type_code = raw.get("domain_type_code", "")

        # --- Preserve rich metadata in .raw ---
        preserved_raw: dict[str, Any] = {}
        if domain_type_code:
            preserved_raw["domain_type_code"] = domain_type_code
        if hierarchy_raw:
            preserved_raw["hierarchy"] = hierarchy_raw
        platform_meta = raw.get("platform_meta")
        if platform_meta:
            preserved_raw["platform_meta"] = platform_meta
        crawl_keyword = raw.get("crawl_keyword", "")
        if crawl_keyword:
            preserved_raw["crawl_keyword"] = crawl_keyword
        if content_raw.get("title"):
            preserved_raw["content_title"] = content_raw.get("title")
        if content_raw.get("subtitle"):
            preserved_raw["content_subtitle"] = content_raw.get("subtitle")
        if content_raw.get("keywords"):
            preserved_raw["content_keywords"] = content_raw.get("keywords")
        task_id = identity.get("task_id", "")
        if task_id:
            preserved_raw["task_id"] = task_id

        return cls(
            uap_version="",  # ingest-srv does not emit uap_version
            event_id=uap_id,
            domain_type_code=domain_type_code,
            ingest=UAPIngest(
                project_id=project_id,
                source=UAPSource(
                    source_id=identity.get("origin_id", ""),
                    source_type=identity.get("platform", ""),
                ),
                batch=UAPBatch(
                    received_at=temporal_raw.get("ingested_at", ""),
                ),
                trace=UAPTrace(
                    mapping_id=task_id,
                ),
            ),
            content=UAPContent(
                doc_id=uap_id,
                doc_type=(identity.get("uap_type") or "post").lower(),
                text=content_raw.get("text", ""),
                url=identity.get("url"),
                language=content_raw.get("language"),
                published_at=temporal_raw.get("posted_at"),
                author=UAPAuthor(
                    author_id=author_raw.get("id"),
                    display_name=author_raw.get("nickname"),
                    username=author_raw.get("username"),
                    avatar_url=author_raw.get("avatar"),
                    is_verified=bool(author_raw.get("is_verified", False)),
                ),
                parent=UAPParent(
                    parent_id=hierarchy_raw.get("parent_id"),
                    parent_type=None,
                ),
                attachments=attachments,
            ),
            signals=UAPSignals(
                engagement=UAPEngagement(
                    like_count=cls._safe_int(engagement_raw.get("likes")),
                    comment_count=cls._safe_int(engagement_raw.get("comments_count")),
                    share_count=cls._safe_int(engagement_raw.get("shares")),
                    view_count=cls._safe_int(engagement_raw.get("views")),
                    save_count=cls._safe_int(engagement_raw.get("saves")),
                ),
            ),
            context=UAPContext(
                keywords_matched=keywords_matched,
            ),
            raw=preserved_raw,
        )

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
