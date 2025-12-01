"""Message queue consumer entry point for Analytics Engine."""

import json
from typing import Optional, Callable, Any, TYPE_CHECKING

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
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from services.analytics.impact import ImpactCalculator


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

    impact_calculator = ImpactCalculator()

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

                # Parse JSON
                data = json.loads(body)

                # Log message metadata
                post_id = data.get("meta", {}).get("id", "unknown")
                platform = data.get("meta", {}).get("platform", "UNKNOWN")
                logger.info(f"Processing post {post_id} from {platform}")

                # Extract text content
                title = data.get("content", {}).get("title", "")
                text = data.get("content", {}).get("text", "")
                combined_text = f"{title} {text}".strip()

                # Process with AI models if available
                sentiment_overall: dict[str, Any] | None = None
                if spacyyake and combined_text:
                    logger.info("Extracting keywords...")
                    keyword_result = spacyyake.extract(combined_text)
                    if keyword_result.success:
                        logger.info(f"Extracted {len(keyword_result.keywords)} keywords")
                    else:
                        logger.warning(f"Keyword extraction failed: {keyword_result.error_message}")

                if phobert and combined_text:
                    logger.info("Analyzing sentiment...")
                    sentiment_result = phobert.predict(combined_text)
                    sentiment_overall = sentiment_result.get("overall") or sentiment_result
                    logger.info(
                        "Sentiment: %s (score=%s)",
                        sentiment_overall.get("label", sentiment_result.get("sentiment", "unknown")),
                        sentiment_overall.get("score"),
                    )

                # Compute impact & risk if we have minimal inputs
                try:
                    interaction = data.get("metrics", {}) or {}
                    author = data.get("author", {}) or {}

                    if sentiment_overall is not None and interaction and author:
                        impact_result = impact_calculator.calculate(
                            interaction=interaction,
                            author=author,
                            sentiment=sentiment_overall,
                            platform=platform,
                        )
                        logger.info(
                            "Impact calculated: score=%s, risk=%s, viral=%s, kol=%s",
                            impact_result["impact_score"],
                            impact_result["risk_level"],
                            impact_result["is_viral"],
                            impact_result["is_kol"],
                        )
                    else:
                        logger.info(
                            "Skipping impact calculation (missing sentiment/metrics/author)."
                        )
                except Exception as e:  # pragma: no cover - defensive logging
                    logger.error(f"Impact calculation failed: {e}")

                # TODO: Save results to database (future work)
                logger.info(f"Message processed successfully: {post_id}")

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
