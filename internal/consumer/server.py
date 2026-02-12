import asyncio
import importlib
from typing import Dict, List

from pkg.rabbitmq.consumer import RabbitMQClient
from pkg.rabbitmq.type import RabbitMQConfig as RabbitMQClientConfig

from .interface import IConsumerServer
from .type import Dependencies


class ConsumerServer(IConsumerServer):
    """Consumer server with multi-queue support.

    This server manages multiple RabbitMQ consumers, each handling different
    queues with their own domain-specific handlers.

    Architecture:
    - 1 server manages N consumers
    - Each consumer connects to 1 queue
    - Each queue has its own handler (from domain layer)
    - All consumers run concurrently via asyncio.gather
    """

    def __init__(self, deps: Dependencies):
        """Initialize consumer server.

        Args:
            deps: Service dependencies
        """
        self.deps = deps
        self.logger = deps.logger
        self._running = False

        # Consumer management
        self.consumers: List[RabbitMQClient] = []
        self.handlers: Dict[str, any] = {}
        self.consumer_tasks: List[asyncio.Task] = []

        # Domain services registry
        self.registry = None
        self.domain_services = None

    async def start(self) -> None:
        """Start all configured queue consumers.

        This method:
        1. Initializes domain services via registry
        2. Loads handler classes dynamically from config
        3. Creates RabbitMQ consumers for each queue
        4. Starts consuming from all queues concurrently

        Raises:
            Exception: If server fails to start
        """
        try:
            # Initialize domain services via registry
            from .registry import ConsumerRegistry

            self.registry = ConsumerRegistry(self.deps)
            self.domain_services = self.registry.initialize()
            self.logger.info("Domain services initialized via registry")

            queue_configs = self.deps.config.rabbitmq.queues

            if not queue_configs:
                self.logger.warn(
                    "No queues configured, server will not consume messages"
                )
                return

            self.logger.info(
                f"Starting consumer server with {len(queue_configs)} queue(s)"
            )

            # Initialize consumers and handlers for each queue
            for queue_config in queue_configs:
                if not queue_config.enabled:
                    self.logger.info(
                        f"Queue '{queue_config.name}' is disabled, skipping"
                    )
                    continue

                # Get handler from domain services (already initialized in registry)
                handler = self._get_handler_from_services(
                    queue_config.handler_module,
                    queue_config.handler_class,
                )

                # Create consumer for this queue
                consumer = RabbitMQClient(
                    RabbitMQClientConfig(
                        url=self.deps.config.rabbitmq.url,
                        queue_name=queue_config.name,
                        exchange_name=queue_config.exchange,
                        routing_key=queue_config.routing_key,
                        prefetch_count=queue_config.prefetch_count,
                    )
                )

                await consumer.connect()

                self.consumers.append(consumer)
                self.handlers[queue_config.name] = handler

                self.logger.info(
                    f"Initialized consumer for queue '{queue_config.name}' "
                    f"(exchange: {queue_config.exchange}, routing_key: {queue_config.routing_key})"
                )

            if not self.consumers:
                self.logger.warn(
                    "No enabled queues found, server will not consume messages"
                )
                return

            # Start consuming from all queues concurrently
            self._running = True
            self.logger.info("Consumer server started, waiting for messages...")

            # Create tasks for each consumer
            consume_tasks = []
            for consumer, (queue_name, handler) in zip(
                self.consumers, self.handlers.items()
            ):
                task = asyncio.create_task(
                    consumer.consume(handler.handle), name=f"consumer-{queue_name}"
                )
                consume_tasks.append(task)
                self.consumer_tasks.append(task)

            # Wait for all consumers (blocks until shutdown)
            await asyncio.gather(*consume_tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"Failed to start consumer server: {e}")
            self.logger.exception("Server start error:")
            raise

    async def shutdown(self) -> None:
        """Shutdown the consumer server gracefully.

        This method:
        1. Stops consuming new messages
        2. Cancels all consumer tasks
        3. Closes all RabbitMQ connections
        4. Cleans up domain services
        5. Cleans up resources
        """
        try:
            self.logger.info("Shutting down consumer server...")
            self._running = False

            # Cancel all consumer tasks
            for task in self.consumer_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete cancellation
            if self.consumer_tasks:
                await asyncio.gather(*self.consumer_tasks, return_exceptions=True)

            # Close all RabbitMQ connections
            for consumer in self.consumers:
                await consumer.close()

            # Cleanup domain services
            if self.registry:
                self.registry.shutdown()

            self.logger.info("Consumer server shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.logger.exception("Shutdown error:")

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running, False otherwise
        """
        return self._running

    def _get_handler_from_services(self, module_path: str, class_name: str):
        """Get handler from domain services.

        Args:
            module_path: Python module path (for logging/validation)
            class_name: Handler class name (for logging/validation)

        Returns:
            Handler instance from domain services

        Raises:
            ValueError: If handler not found in domain services
        """
        # Map handler class names to domain services attributes
        handler_map = {
            "AnalyticsHandler": "analytics_handler",
            # Add more handlers here as needed
        }
        
        handler_attr = handler_map.get(class_name)
        if not handler_attr:
            raise ValueError(
                f"Handler '{class_name}' not registered in handler_map. "
                f"Available handlers: {list(handler_map.keys())}"
            )
        
        handler = getattr(self.domain_services, handler_attr, None)
        if handler is None:
            raise ValueError(
                f"Handler '{handler_attr}' not found in domain services. "
                f"Make sure it's initialized in ConsumerRegistry."
            )
        
        self.logger.info(f"Loaded handler: {module_path}.{class_name}")
        return handler

    def _load_handler(self, module_path: str, class_name: str, domain_services):
        """Load handler class dynamically from module path.

        Args:
            module_path: Python module path (e.g., "internal.analytics.delivery.rabbitmq.handler")
            class_name: Handler class name (e.g., "AnalyticsHandler")
            domain_services: Domain services from registry

        Returns:
            Handler instance

        Raises:
            ImportError: If module or class cannot be loaded
        """
        try:
            # Import module
            module = importlib.import_module(module_path)

            # Get class from module
            handler_class = getattr(module, class_name)

            # Instantiate handler with dependencies and domain services
            handler = handler_class(self.deps, domain_services)

            self.logger.info(f"Loaded handler: {module_path}.{class_name}")

            return handler

        except ImportError as e:
            self.logger.error(f"Failed to import handler module '{module_path}': {e}")
            raise
        except AttributeError as e:
            self.logger.error(
                f"Handler class '{class_name}' not found in module '{module_path}': {e}"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to instantiate handler '{class_name}': {e}")
            raise


__all__ = ["ConsumerServer"]
