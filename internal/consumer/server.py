from .interface import IConsumerServer
from .type import Dependencies
from .handler import MessageHandler


class ConsumerServer(IConsumerServer):
    """Consumer server implementation.

    This server:
    1. Receives dependencies from main
    2. Creates message handlers
    3. Registers handlers with message broker
    4. Manages server lifecycle (start/shutdown)
    """

    def __init__(self, deps: Dependencies):
        """Initialize consumer server with dependencies.

        Args:
            deps: Dependencies struct containing all service instances
        """
        self.deps = deps
        self.logger = deps.logger
        self._running = False

        # Create message handler
        self.message_handler = MessageHandler(deps)

    async def start(self) -> None:
        """Start the consumer server.

        This method:
        1. Connects to RabbitMQ
        2. Registers message handlers
        3. Starts consuming messages

        Raises:
            Exception: If server fails to start
        """
        try:
            self.logger.info("Starting consumer server...")

            # Connect to RabbitMQ
            await self.deps.rabbitmq.connect()
            self.logger.info("Connected to RabbitMQ")

            # Register handlers
            self._register_handlers()

            # Start consuming messages
            self._running = True
            self.logger.info("Consumer server started, waiting for messages...")

            # Start consuming with registered handler
            await self.deps.rabbitmq.consume(
                self.message_handler.handle_analytics_message
            )

        except Exception as e:
            self.logger.error(f"Failed to start consumer server: {e}")
            self.logger.exception("Server start error:")
            raise

    async def shutdown(self) -> None:
        """Shutdown the consumer server gracefully.

        This method:
        1. Stops consuming new messages
        2. Closes RabbitMQ connection
        3. Cleans up resources
        """
        try:
            self.logger.info("Shutting down consumer server...")
            self._running = False

            # Close RabbitMQ connection
            await self.deps.rabbitmq.close()

            self.logger.info("Consumer server shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.logger.exception("Shutdown error:")

    def _register_handlers(self) -> None:
        """Register message handlers.

        This is where you register different handlers for different
        message types or routing keys. Currently we have one handler
        for analytics messages.

        In the future, you can add more handlers:
        - self.batch_handler for batch processing
        - self.priority_handler for high-priority messages
        - etc.
        """
        self.logger.info("Registering message handlers...")
        self.logger.info("- Analytics message handler registered")
        # Future: Register additional handlers here
        self.logger.info("All message handlers registered")

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running, False otherwise
        """
        return self._running


__all__ = ["ConsumerServer"]
