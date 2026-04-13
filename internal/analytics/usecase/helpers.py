import uuid
from datetime import datetime, timezone
from typing import Any, Optional

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


def add_uap_metadata(
    result: AnalyticsResult,
    uap: UAPRecord,
    config: Config,
) -> None:
    # Content fields
    if uap.content:
        result.content_text = uap.content.text
        result.permalink = uap.content.url

        # Author fields
        if uap.content.author:
            result.author_id = uap.content.author.author_id
            result.author_name = uap.content.author.display_name
            result.author_username = uap.content.author.username
            result.author_avatar_url = uap.content.author.avatar_url
            result.author_is_verified = uap.content.author.is_verified

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
