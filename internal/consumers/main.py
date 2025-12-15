"""Message queue consumer entry point for Analytics Engine.

Processes data.collected events from smap.events exchange with batch processing.
Publishes analyze results to Collector service via RabbitMQ.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Callable, Any, List, TYPE_CHECKING, Iterator

try:
    from aio_pika import IncomingMessage  # type: ignore

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    if TYPE_CHECKING:
        from aio_pika import IncomingMessage  # type: ignore
    else:
        IncomingMessage = Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.logger import logger
from core.config import settings
from core.constants import categorize_error
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from infrastructure.messaging.publisher import RabbitMQPublisher, RabbitMQPublisherError
from infrastructure.storage.minio_client import (
    MinioAdapter,
    MinioAdapterError,
    MinioObjectNotFoundError,
    MinioDecompressionError,
)
from models.database import Base
from models.messages import (
    AnalyzeResultMessage,
    AnalyzeResultPayload,
    AnalyzeItem,
    AnalyzeError,
    create_error_result,
)
from repository.analytics_repository import AnalyticsRepository, AnalyticsRepositoryError
from repository.crawl_error_repository import CrawlErrorRepository
from services.analytics.orchestrator import AnalyticsOrchestrator
from utils.project_id_extractor import extract_project_id


def parse_minio_path(minio_path: str) -> tuple[str, str]:
    """Parse MinIO path into bucket and object path.

    Args:
        minio_path: Full MinIO path. Supports formats:
            - "crawl-results/tiktok/2025/12/06/batch.json" (simple)
            - "minio://crawl-results/tiktok/2025/12/06/batch.json" (URL format)

    Returns:
        Tuple of (bucket, object_path)

    Raises:
        ValueError: If path format is invalid
    """
    if not minio_path:
        raise ValueError("minio_path cannot be empty")

    # Strip minio:// prefix if present
    if minio_path.startswith("minio://"):
        minio_path = minio_path[8:]  # len("minio://") = 8

    parts = minio_path.split("/", 1)
    if len(parts) < 2:
        raise ValueError(f"Invalid minio_path format: {minio_path}")

    bucket = parts[0]
    object_path = parts[1]

    if not bucket or not object_path:
        raise ValueError(f"Invalid minio_path format: {minio_path}")

    return bucket, object_path


def validate_event_format(envelope: dict[str, Any]) -> bool:
    """Validate that envelope is a valid data.collected event.

    Args:
        envelope: Parsed JSON message envelope

    Returns:
        True if valid event format, False otherwise
    """
    if "payload" not in envelope or not isinstance(envelope.get("payload"), dict):
        return False

    payload = envelope["payload"]
    return "minio_path" in payload


def parse_event_metadata(envelope: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata from data.collected event.

    Args:
        envelope: Event envelope

    Returns:
        Dictionary with event metadata
    """
    payload = envelope.get("payload", {})

    return {
        "event_id": envelope.get("event_id"),
        "event_type": envelope.get("event_type"),
        "timestamp": envelope.get("timestamp"),
        "minio_path": payload.get("minio_path"),
        "project_id": payload.get("project_id"),
        "job_id": payload.get("job_id"),
        "batch_index": payload.get("batch_index"),
        "content_count": payload.get("content_count"),
        "platform": payload.get("platform"),
        "task_type": payload.get("task_type"),
        "keyword": payload.get("keyword"),
    }


def _create_session_factory() -> sessionmaker:
    """Create a synchronous SQLAlchemy session factory."""
    engine = create_engine(settings.database_url_sync)
    Base.metadata.bind = engine
    return sessionmaker(bind=engine)


@contextmanager
def _db_session(session_factory: sessionmaker) -> Iterator[Session]:
    """Context manager yielding a DB session and ensuring cleanup."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def build_result_items(processed_results: List[dict[str, Any]]) -> List[AnalyzeItem]:
    """Build AnalyzeItem list from processed results.

    Args:
        processed_results: List of processing results with status="success"

    Returns:
        List of AnalyzeItem for successful items
    """
    items = []
    for result in processed_results:
        if result.get("status") == "success":
            items.append(
                AnalyzeItem(
                    content_id=result.get("content_id", "unknown"),
                    sentiment=result.get("sentiment"),
                    sentiment_score=result.get("sentiment_score"),
                    impact_score=result.get("impact_score"),
                )
            )
    return items


def build_error_items(processed_results: List[dict[str, Any]]) -> List[AnalyzeError]:
    """Build AnalyzeError list from processed results.

    Args:
        processed_results: List of processing results with status="error"

    Returns:
        List of AnalyzeError for failed items
    """
    errors = []
    for result in processed_results:
        if result.get("status") == "error":
            errors.append(
                AnalyzeError(
                    content_id=result.get("content_id", "unknown"),
                    error=result.get("error_message") or result.get("error_code", "Unknown error"),
                )
            )
    return errors


def create_message_handler(
    phobert: Optional[PhoBERTONNX],
    spacyyake: Optional[SpacyYakeExtractor],
    publisher: Optional[RabbitMQPublisher] = None,
) -> Callable[[IncomingMessage], None]:
    """Create message handler with AI model instances and optional publisher.

    This factory function creates a message handler that has access to
    the AI model instances passed in. The handler will process incoming
    data.collected events from RabbitMQ with batch processing.

    If publisher is provided and settings.publish_enabled is True,
    results will be published to Collector service after processing.

    Args:
        phobert: PhoBERT model instance (may be None if initialization failed)
        spacyyake: SpaCy-YAKE extractor instance (may be None if initialization failed)
        publisher: RabbitMQ publisher for sending results to Collector (optional)

    Returns:
        Async callable that processes incoming messages
    """

    minio_adapter = MinioAdapter()
    session_factory = _create_session_factory()
    publish_enabled = settings.publish_enabled and publisher is not None

    if publish_enabled:
        logger.info("Result publishing enabled (exchange=%s)", settings.publish_exchange)
    else:
        logger.info("Result publishing disabled")

    async def process_event_format(envelope: dict[str, Any], db: Session) -> dict[str, Any]:
        """Process new event format (data.collected).

        Args:
            envelope: Event envelope with payload.minio_path
            db: Database session

        Returns:
            Processing result with success/error counts
        """
        event_metadata = parse_event_metadata(envelope)
        event_id = event_metadata.get("event_id", "unknown")
        minio_path = event_metadata.get("minio_path")
        job_id = event_metadata.get("job_id", "")
        project_id = extract_project_id(job_id) or event_metadata.get("project_id")
        expected_item_count = event_metadata.get("content_count", 0)

        logger.info(
            "Processing event: event_id=%s, job_id=%s, batch_index=%s",
            event_id,
            job_id,
            event_metadata.get("batch_index"),
        )

        if not minio_path:
            raise ValueError("Event missing minio_path in payload")

        # Parse MinIO path
        bucket, object_path = parse_minio_path(minio_path)
        logger.debug("Fetching batch from MinIO: %s/%s", bucket, object_path)

        # Fetch batch data from MinIO
        try:
            batch_items = minio_adapter.download_batch(bucket, object_path)
        except (MinioAdapterError, MinioObjectNotFoundError, MinioDecompressionError) as exc:
            # MinIO fetch failed - publish error result if enabled
            logger.error("MinIO fetch failed for event_id=%s: %s", event_id, exc)

            if publish_enabled and publisher:
                await _publish_error_result(
                    publisher=publisher,
                    project_id=project_id,
                    job_id=job_id,
                    batch_size=expected_item_count or 1,
                    error_message=f"MinIO fetch failed: {exc}",
                )

            raise  # Re-raise to trigger message nack

        # Validate batch size
        platform = event_metadata.get("platform", "unknown")
        expected_size = (
            settings.expected_batch_size_tiktok
            if platform.lower() == "tiktok"
            else settings.expected_batch_size_youtube
        )
        if len(batch_items) != expected_size:
            logger.warning(
                "Unexpected batch size: expected=%d, actual=%d, platform=%s, job_id=%s",
                expected_size,
                len(batch_items),
                platform,
                job_id,
            )

        # Process batch items
        analytics_repo = AnalyticsRepository(db)
        error_repo = CrawlErrorRepository(db)

        success_count = 0
        error_count = 0
        error_distribution: dict[str, int] = {}
        processed_results: List[dict[str, Any]] = []

        for item in batch_items:
            try:
                result = process_single_item(
                    item=item,
                    event_metadata=event_metadata,
                    project_id=project_id,
                    analytics_repo=analytics_repo,
                    error_repo=error_repo,
                    phobert=phobert,
                )

                processed_results.append(result)

                if result.get("status") == "success":
                    success_count += 1
                else:
                    error_count += 1
                    error_code = result.get("error_code", "UNKNOWN_ERROR")
                    error_distribution[error_code] = error_distribution.get(error_code, 0) + 1

            except Exception as exc:
                logger.error(
                    "Error processing item in batch: event_id=%s, error=%s",
                    event_id,
                    exc,
                )
                error_count += 1
                processed_results.append(
                    {
                        "status": "error",
                        "content_id": "unknown",
                        "error_code": "INTERNAL_ERROR",
                        "error_message": str(exc),
                    }
                )

        logger.info(
            "Batch completed: event_id=%s, job_id=%s, success=%d, errors=%d",
            event_id,
            job_id,
            success_count,
            error_count,
        )

        # Publish result to Collector if enabled
        if publish_enabled and publisher:
            await _publish_batch_result(
                publisher=publisher,
                project_id=project_id,
                job_id=job_id,
                batch_size=len(batch_items),
                success_count=success_count,
                error_count=error_count,
                processed_results=processed_results,
            )

        return {
            "event_id": event_id,
            "job_id": job_id,
            "success_count": success_count,
            "error_count": error_count,
            "error_distribution": error_distribution,
        }

    async def _publish_batch_result(
        publisher: RabbitMQPublisher,
        project_id: Optional[str],
        job_id: str,
        batch_size: int,
        success_count: int,
        error_count: int,
        processed_results: List[dict[str, Any]],
    ) -> None:
        """Publish batch result to Collector service.

        Args:
            publisher: RabbitMQ publisher instance
            project_id: Project identifier
            job_id: Job identifier
            batch_size: Total items in batch
            success_count: Successfully processed items
            error_count: Failed items
            processed_results: List of individual processing results
        """
        try:
            result_msg = AnalyzeResultMessage(
                success=error_count < batch_size,
                payload=AnalyzeResultPayload(
                    project_id=project_id,
                    job_id=job_id,
                    task_type="analyze_result",
                    batch_size=batch_size,
                    success_count=success_count,
                    error_count=error_count,
                    results=build_result_items(processed_results),
                    errors=build_error_items(processed_results),
                ),
            )

            await publisher.publish_analyze_result(result_msg)

        except RabbitMQPublisherError as exc:
            # Log error but don't fail the batch processing
            logger.error("Failed to publish batch result: %s", exc)

    async def _publish_error_result(
        publisher: RabbitMQPublisher,
        project_id: Optional[str],
        job_id: str,
        batch_size: int,
        error_message: str,
    ) -> None:
        """Publish batch-level error result to Collector service.

        Args:
            publisher: RabbitMQ publisher instance
            project_id: Project identifier
            job_id: Job identifier
            batch_size: Expected items in batch (all marked as failed)
            error_message: Description of the batch-level error
        """
        try:
            error_msg = create_error_result(
                project_id=project_id,
                job_id=job_id,
                batch_size=batch_size,
                error_message=error_message,
            )

            await publisher.publish_analyze_result(error_msg)

        except RabbitMQPublisherError as exc:
            # Log error but don't fail - the original error will be raised
            logger.error("Failed to publish error result: %s", exc)

    async def message_handler(message: IncomingMessage) -> None:
        """Process incoming data.collected event from RabbitMQ."""
        async with message.process():
            event_id = "unknown"
            try:
                # Decode message body
                body = message.body.decode("utf-8")
                logger.info("Received message: %s...", body[:100])

                # Parse JSON envelope
                try:
                    envelope = json.loads(body)
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON in message: %s", exc)
                    raise

                # Validate event format
                if not validate_event_format(envelope):
                    raise ValueError("Invalid event format: missing payload.minio_path")

                event_id = envelope.get("event_id", "unknown")

                with _db_session(session_factory) as db:
                    result = await process_event_format(envelope, db)
                    logger.info(
                        "Event processed: event_id=%s, success=%d, errors=%d",
                        result.get("event_id"),
                        result.get("success_count", 0),
                        result.get("error_count", 0),
                    )

            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Validation error for event_id=%s: %s", event_id, exc)
                raise

            except (MinioAdapterError, AnalyticsRepositoryError) as exc:
                logger.error("Infrastructure error for event_id=%s: %s", event_id, exc)
                raise

            except Exception as exc:
                logger.error("Unexpected error processing event_id=%s: %s", event_id, exc)
                logger.exception("Message processing error details:")
                raise

    return message_handler


def process_single_item(
    item: dict[str, Any],
    event_metadata: dict[str, Any],
    project_id: Optional[str],
    analytics_repo: AnalyticsRepository,
    error_repo: CrawlErrorRepository,
    phobert: Optional[PhoBERTONNX],
) -> dict[str, Any]:
    """Process a single item from a batch.

    Args:
        item: Single item data from batch
        event_metadata: Event metadata for context
        project_id: Extracted project ID
        analytics_repo: Analytics repository instance
        error_repo: Error repository instance
        phobert: PhoBERT model instance

    Returns:
        Processing result with status
    """
    meta = item.get("meta") or {}
    content_id = meta.get("id", "unknown")
    fetch_status = meta.get("fetch_status", "success")
    platform = meta.get("platform", event_metadata.get("platform", "unknown"))

    # Handle error items
    if fetch_status == "error":
        error_code = meta.get("error_code", "UNKNOWN_ERROR")
        error_message = meta.get("error_message", "")
        error_details = meta.get("error_details", {})

        # Save error record
        error_data = {
            "content_id": content_id,
            "project_id": project_id,
            "job_id": event_metadata.get("job_id", ""),
            "platform": platform,
            "error_code": error_code,
            "error_message": error_message,
            "error_details": error_details,
            "permalink": meta.get("permalink"),
        }

        try:
            error_repo.save(error_data)
            logger.debug(
                "Saved error record: content_id=%s, error_code=%s",
                content_id,
                error_code,
            )
        except Exception as exc:
            logger.error("Failed to save error record: %s", exc)

        return {
            "status": "error",
            "content_id": content_id,
            "error_code": error_code,
        }

    # Handle success items - run analytics pipeline
    try:
        orchestrator = AnalyticsOrchestrator(
            repository=analytics_repo,
            sentiment_analyzer=None,
        )

        # Enrich item with batch context
        enriched_item = enrich_with_batch_context(item, event_metadata, project_id)

        result = orchestrator.process_post(enriched_item)

        return {
            "status": "success",
            "content_id": content_id,
            "impact_score": result.get("impact_score", 0.0),
        }

    except Exception as exc:
        logger.error("Error processing item %s: %s", content_id, exc)
        return {
            "status": "error",
            "content_id": content_id,
            "error_code": "INTERNAL_ERROR",
            "error_message": str(exc),
        }


def enrich_with_batch_context(
    item: dict[str, Any],
    event_metadata: dict[str, Any],
    project_id: Optional[str],
) -> dict[str, Any]:
    """Enrich item with batch context from event metadata.

    Args:
        item: Original item data
        event_metadata: Event metadata
        project_id: Extracted project ID

    Returns:
        Enriched item with batch context
    """
    enriched = item.copy()

    # Add batch context to meta
    meta = enriched.get("meta", {}).copy()
    meta["job_id"] = event_metadata.get("job_id")
    meta["batch_index"] = event_metadata.get("batch_index")
    meta["task_type"] = event_metadata.get("task_type")
    meta["keyword_source"] = event_metadata.get("keyword")
    meta["pipeline_version"] = f"crawler_{meta.get('platform', 'unknown').lower()}_v3"

    if project_id:
        meta["project_id"] = project_id

    # Parse crawled_at timestamp
    timestamp = event_metadata.get("timestamp")
    if timestamp:
        try:
            meta["crawled_at"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    enriched["meta"] = meta
    return enriched
