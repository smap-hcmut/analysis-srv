"""Presenters for analytics delivery layer.

Convention: Mappers between delivery DTOs and domain Input/Output.
- to_input(): Delivery DTO → UseCase Input
- new_*_resp(): UseCase Output → Delivery Response DTO
"""

from typing import Any, Optional

from internal.analytics.type import Input, PostData, EventMetadata
from internal.analytics.delivery.type import (
    DataCollectedMessage,
    PostPayload,
    EventPayloadMetadata,
)
from internal.analytics.delivery.constant import (
    FIELD_EVENT_ID,
    FIELD_EVENT_TYPE,
    FIELD_TIMESTAMP,
    FIELD_PAYLOAD,
    FIELD_META,
    FIELD_CONTENT,
    FIELD_INTERACTION,
    FIELD_AUTHOR,
    FIELD_COMMENTS,
    FIELD_MINIO_PATH,
    FIELD_PROJECT_ID,
    FIELD_JOB_ID,
    FIELD_BATCH_INDEX,
    FIELD_PLATFORM,
    FIELD_TASK_TYPE,
    FIELD_BRAND_NAME,
    FIELD_KEYWORD,
)


def parse_message(envelope: dict[str, Any]) -> DataCollectedMessage:
    """Parse raw JSON envelope into delivery DTO.

    Args:
        envelope: Raw parsed JSON from message body

    Returns:
        DataCollectedMessage DTO
    """
    return DataCollectedMessage(
        event_id=envelope.get(FIELD_EVENT_ID, ""),
        event_type=envelope.get(FIELD_EVENT_TYPE, ""),
        timestamp=envelope.get(FIELD_TIMESTAMP, ""),
        payload=envelope.get(FIELD_PAYLOAD, {}),
    )


def parse_event_metadata(msg: DataCollectedMessage) -> EventPayloadMetadata:
    """Extract event metadata from delivery DTO.

    Args:
        msg: Parsed delivery message

    Returns:
        EventPayloadMetadata DTO
    """
    payload = msg.payload
    return EventPayloadMetadata(
        project_id=payload.get(FIELD_PROJECT_ID),
        job_id=payload.get(FIELD_JOB_ID),
        batch_index=payload.get(FIELD_BATCH_INDEX),
        platform=payload.get(FIELD_PLATFORM),
        task_type=payload.get(FIELD_TASK_TYPE),
        brand_name=payload.get(FIELD_BRAND_NAME),
        keyword=payload.get(FIELD_KEYWORD),
        minio_path=payload.get(FIELD_MINIO_PATH),
    )


def parse_post_payload(msg: DataCollectedMessage) -> PostPayload:
    """Extract post data from delivery DTO.

    Args:
        msg: Parsed delivery message

    Returns:
        PostPayload DTO
    """
    payload = msg.payload
    return PostPayload(
        meta=payload.get(FIELD_META, {}),
        content=payload.get(FIELD_CONTENT, {}),
        interaction=payload.get(FIELD_INTERACTION, {}),
        author=payload.get(FIELD_AUTHOR, {}),
        comments=payload.get(FIELD_COMMENTS, []),
    )


def to_pipeline_input(
    msg: DataCollectedMessage,
    post: PostPayload,
    meta: EventPayloadMetadata,
) -> Input:
    """Convert delivery DTOs to domain Input.

    Convention: Mapper from Delivery DTO → UseCase Input.

    Args:
        msg: Parsed delivery message
        post: Extracted post payload
        meta: Extracted event metadata

    Returns:
        Domain Input for analytics pipeline
    """
    return Input(
        post_data=PostData(
            meta=post.meta,
            content=post.content,
            interaction=post.interaction,
            author=post.author,
            comments=post.comments,
        ),
        event_metadata=EventMetadata(
            event_id=msg.event_id,
            event_type=msg.event_type,
            timestamp=msg.timestamp,
            minio_path=meta.minio_path,
            project_id=meta.project_id,
            job_id=meta.job_id,
            batch_index=meta.batch_index,
            platform=meta.platform,
            task_type=meta.task_type,
            brand_name=meta.brand_name,
            keyword=meta.keyword,
        ),
        project_id=_extract_project_id(meta),
    )


def _extract_project_id(meta: EventPayloadMetadata) -> Optional[str]:
    """Extract project_id from metadata."""
    if meta.project_id:
        return meta.project_id

    if meta.job_id and "-" in meta.job_id:
        parts = meta.job_id.split("-", 1)
        if len(parts[0]) == 36:
            return parts[0]

    return None


__all__ = [
    "parse_message",
    "parse_event_metadata",
    "parse_post_payload",
    "to_pipeline_input",
]
