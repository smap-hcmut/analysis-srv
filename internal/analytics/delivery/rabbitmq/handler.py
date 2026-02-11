import json
from aio_pika import IncomingMessage

from internal.consumer.type import Dependencies
from internal.analytics.usecase import AnalyticsUseCase


class AnalyticsHandler:
    """Handler for analytics events from RabbitMQ.

    This handler:
    - Receives messages from analytics queue
    - Parses and validates message format
    - Delegates processing to use case layer
    - Handles message acknowledgment
    """

    def __init__(self, deps: Dependencies):
        """Initialize analytics handler.

        Args:
            deps: Service dependencies
        """
        self.deps = deps
        self.logger = deps.logger
        self.usecase = AnalyticsUseCase(deps)

    async def handle(self, message: IncomingMessage) -> None:
        """Handle incoming analytics message.

        Args:
            message: Incoming RabbitMQ message
        """
        async with message.process():
            try:
                # Parse message body
                body = message.body.decode("utf-8")
                data = json.loads(body)

                message_id = data.get("id", "unknown")
                self.logger.info(f"[Analytics] Processing message: {message_id}")

                # Delegate to use case
                await self.usecase.process_analytics(data)

                self.logger.info(f"[Analytics] Message processed: {message_id}")

            except json.JSONDecodeError as e:
                self.logger.error(f"[Analytics] Invalid JSON: {e}")
                raise

            except Exception as e:
                self.logger.error(f"[Analytics] Processing error: {e}")
                self.logger.exception("[Analytics] Error details:")
                raise


__all__ = ["AnalyticsHandler"]
