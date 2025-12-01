"""Message queue consumer entry point for Analytics Engine."""

import json
from contextlib import contextmanager
from typing import Optional, Callable, Any, TYPE_CHECKING, Iterator

try:
    from aio_pika import IncomingMessage  # type: ignore

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    if TYPE_CHECKING:
        from aio_pika import IncomingMessage  # type: ignore
    else:
        IncomingMessage = Any

from core.logger import logger
from core.config import settings
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from infrastructure.storage.minio_client import MinioAdapter
from models.database import Base
from repositories.analytics_repository import AnalyticsRepository
from services.analytics.orchestrator import AnalyticsOrchestrator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


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


def create_message_handler(
    phobert: Optional[PhoBERTONNX], spacyyake: Optional[SpacyYakeExtractor]
) -> Callable[[IncomingMessage], None]:
    """Create message handler with AI model instances.

    This factory function creates a message handler that has access to
    the AI model instances passed in. The handler will process incoming
    messages from RabbitMQ.

    Args:
        phobert: PhoBERT model instance (may be None if initialization failed)
        spacyyake: SpaCy-YAKE extractor instance (may be None if initialization failed)

    Returns:
        Async callable that processes incoming messages

    Example:
        >>> handler = create_message_handler(phobert, spacyyake)
        >>> await rabbitmq_client.consume(handler)
    """

    minio_adapter = MinioAdapter()
    session_factory = _create_session_factory()

    async def message_handler(message: IncomingMessage) -> None:
        """Process incoming message from RabbitMQ.

        Args:
            message: Incoming message from RabbitMQ queue
        """
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                logger.info(f"Received message: {body[:100]}...")

                # Parse JSON envelope
                envelope = json.loads(body)

                # Determine data source: direct post_data or MinIO reference
                post_data: dict[str, Any]
                if "data_ref" in envelope:
                    ref = envelope["data_ref"] or {}
                    bucket = ref.get("bucket")
                    path = ref.get("path")
                    if not bucket or not path:
                        raise ValueError("Invalid data_ref: bucket and path are required")
                    try:
                        # download_json() auto-decompresses if file is compressed
                        post_data = minio_adapter.download_json(bucket, path)
                    except RuntimeError as e:
                        error_msg = str(e)
                        if "decompress" in error_msg.lower():
                            logger.error(
                                "Decompression failed for MinIO object %s/%s: %s",
                                bucket,
                                path,
                                error_msg,
                            )
                            raise ValueError(f"Decompression failed: {error_msg}") from e
                        raise
                else:
                    post_data = envelope

                post_id = post_data.get("meta", {}).get("id", "unknown")
                platform = post_data.get("meta", {}).get("platform", "UNKNOWN")
                logger.info("Processing post %s from %s via orchestrator", post_id, platform)

                # Create DB-backed repository and orchestrator per message
                with _db_session(session_factory) as db:
                    repo = AnalyticsRepository(db)

                    # SentimentAnalyzer is built from provided PhoBERT model if available
                    sentiment_analyzer = None
                    if phobert is not None:
                        sentiment_analyzer = SentimentAnalyzer(phobert)  # type: ignore[name-defined]

                    orchestrator = AnalyticsOrchestrator(
                        repository=repo,
                        sentiment_analyzer=sentiment_analyzer,
                    )
                    result = orchestrator.process_post(post_data)

                logger.info("Message processed successfully and persisted: %s", post_id)

                # Message will be auto-acked when context exits without exception

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in message: {e}")
                # Message will be auto-nacked (rejected)
                raise

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                logger.exception("Message processing error details:")
                # Message will be auto-nacked (rejected)
                raise

    return message_handler
