import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from internal.model.uap import UAPRecord
from internal.post_insight.repository.postgre.helpers import _parse_datetime
from ..type import AnalyticsResult, Config
from ..constant import (
    PLATFORM_UNKNOWN,
    STATUS_ERROR,
    PIPELINE_VERSION_TEMPLATE,
    PIPELINE_VERSION_NUMBER,
)


def normalize_platform(platform: Optional[str]) -> str:
    if not platform:
        return PLATFORM_UNKNOWN
    return str(platform).strip().upper()


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("https://") or value.startswith("http://")
    )


def _with_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _extract_raw_context(uap: UAPRecord) -> dict[str, Any]:
    raw = uap.raw if isinstance(uap.raw, dict) else {}
    context: dict[str, Any] = {}
    for key in ("platform_meta", "hierarchy", "domain_type_code", "crawl_keyword"):
        value = raw.get(key)
        if value:
            context[key] = value
    return context


def _youtube_original_url(uap: UAPRecord, fallback_url: Optional[str]) -> str:
    if _is_http_url(fallback_url):
        return str(fallback_url)

    raw = uap.raw if isinstance(uap.raw, dict) else {}
    platform_meta = raw.get("platform_meta") if isinstance(raw.get("platform_meta"), dict) else {}
    youtube_meta = platform_meta.get("youtube") if isinstance(platform_meta.get("youtube"), dict) else {}
    hierarchy = raw.get("hierarchy") if isinstance(raw.get("hierarchy"), dict) else {}

    source_id = ""
    if uap.ingest and uap.ingest.source:
        source_id = str(uap.ingest.source.source_id or "").strip()

    parent_url = str(youtube_meta.get("parent_url") or "").strip()
    video_id = str(youtube_meta.get("parent_video_id") or "").strip()
    root_id = str(hierarchy.get("root_id") or "").strip()
    if not video_id and root_id.startswith("yt_p_"):
        video_id = root_id.removeprefix("yt_p_")
    if not parent_url and video_id:
        parent_url = f"https://www.youtube.com/watch?v={video_id}"

    doc_type = str(uap.content.doc_type if uap.content else "").strip().lower()
    if _is_http_url(parent_url):
        if doc_type == "comment" and source_id:
            return _with_query_param(parent_url, "lc", source_id)
        return parent_url

    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return ""


def resolve_original_url(uap: UAPRecord) -> str:
    fallback_url = uap.content.url if uap.content else None
    if _is_http_url(fallback_url):
        return str(fallback_url)

    platform = ""
    if uap.ingest and uap.ingest.source:
        platform = str(uap.ingest.source.source_type or "").strip().lower()
    if platform == "youtube":
        return _youtube_original_url(uap, fallback_url)
    return ""


def add_uap_metadata(
    result: AnalyticsResult,
    uap: UAPRecord,
    config: Config,
) -> None:
    # Content fields
    if uap.content:
        result.content_text = uap.content.text
        result.permalink = resolve_original_url(uap) or uap.content.url

        # Author fields
        if uap.content.author:
            result.author_id = uap.content.author.author_id
            result.author_name = uap.content.author.display_name
            result.author_username = uap.content.author.username
            result.author_avatar_url = uap.content.author.avatar_url
            result.author_is_verified = uap.content.author.is_verified

    raw_context = _extract_raw_context(uap)
    if uap.content and uap.content.doc_type:
        raw_context["doc_type"] = uap.content.doc_type
    if raw_context:
        result.raw_context = raw_context

    # Batch context (from ingest)
    if uap.ingest and uap.ingest.batch:
        batch = uap.ingest.batch
        # batch.received_at is string ISO8601
        result.crawled_at = _parse_datetime(batch.received_at)

        # Map batch_id to job_id for backward compatibility
        if batch.batch_id:
            result.job_id = batch.batch_id

    # Entity context (from ingest)
    if uap.ingest and uap.ingest.entity:
        entity = uap.ingest.entity
        result.brand_name = entity.brand
        # Map entity_name to keyword for backward compatibility
        result.keyword = entity.entity_name

    # Pipeline version
    platform = result.platform.lower() if result.platform else "unknown"
    result.pipeline_version = PIPELINE_VERSION_TEMPLATE.format(
        platform=platform, version=PIPELINE_VERSION_NUMBER
    )


def build_error_result(
    uap: UAPRecord,
    project_id: str,
    error_message: str,
) -> AnalyticsResult:
    source_id = None
    platform = PLATFORM_UNKNOWN

    if uap.ingest and uap.ingest.source:
        source_id = uap.ingest.source.source_id
        platform = normalize_platform(uap.ingest.source.source_type)

    return AnalyticsResult(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_id=source_id,
        platform=platform,
        analyzed_at=datetime.now(timezone.utc),
        processing_status=STATUS_ERROR,
    )
