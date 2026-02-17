import json
from aio_pika import IncomingMessage

from .type import Dependencies


class MessageHandler:
    """DEPRECATED: Legacy message handler.

    This handler is no longer used. The active handler is:
    internal/analytics/delivery/rabbitmq/consumer/handler.py (AnalyticsHandler)

    Convention violation: This handler calls pkg infrastructure directly
    (deps.sentiment, deps.keyword_extractor) instead of going through UseCase.
    Kept for reference only — do not use in new code.
    """

    def __init__(self, deps: Dependencies):
        """Initialize message handler with dependencies.

        Args:
            deps: Dependencies struct containing service instances
        """
        self.deps = deps
        self.logger = deps.logger

    async def handle_analytics_message(self, message: IncomingMessage) -> None:
        """Handle incoming analytics message.

        This is the main message processing handler that:
        1. Parses the message
        2. Extracts text
        3. Runs sentiment analysis
        4. Runs keyword extraction
        5. Stores/publishes results

        Args:
            message: Incoming message from RabbitMQ
        """
        async with message.process():
            try:
                # Parse message body
                body = message.body.decode("utf-8")
                data = json.loads(body)

                message_id = data.get("id", "unknown")
                self.logger.info(f"Processing message: {message_id}")

                # Extract text from message
                text = (
                    data.get("text") or data.get("content") or data.get("message", "")
                )

                if not text or not text.strip():
                    self.logger.warning(f"Empty text in message {message_id}, skipping")
                    return

                # Process sentiment analysis
                sentiment_result = self.deps.sentiment.predict(
                    text, return_probabilities=True
                )
                self.logger.info(
                    f"[{message_id}] Sentiment: {sentiment_result.sentiment} "
                    f"(confidence: {sentiment_result.confidence:.2f})"
                )

                # Process keyword extraction
                keyword_result = self.deps.keyword_extractor.extract(text)
                if keyword_result.success:
                    keywords = [kw.keyword for kw in keyword_result.keywords[:5]]
                    self.logger.info(f"[{message_id}] Keywords: {', '.join(keywords)}")
                else:
                    self.logger.warning(
                        f"[{message_id}] Keyword extraction failed: {keyword_result.error_message}"
                    )

                # TODO: Store results in database
                # TODO: Publish results to output queue
                # TODO: Cache results in Redis

                self.logger.info(f"Message processed successfully: {message_id}")

            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON in message: {e}")
                # Message will be nacked due to exception

            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                self.logger.exception("Message processing error:")
                # Message will be nacked due to exception


__all__ = ["MessageHandler"]
