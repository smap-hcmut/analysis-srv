"""Domain registry for consumer application.

This module provides centralized initialization of all domain services
(usecases, repositories) specifically for the consumer application.

Pattern:
- Each app has its own registry
- Registry initializes domain services with proper dependencies
- Services are initialized once and reused throughout the app lifecycle
"""

from dataclasses import dataclass
from typing import Optional

from internal.consumer.type import Dependencies
from internal.text_preprocessing import (
    New as NewTextProcessing,
    Config as TextProcessingConfig,
)
from internal.analytics.usecase import AnalyticsUseCase


@dataclass
class DomainServices:
    """Container for all domain services used by consumer app.

    This struct holds initialized instances of all domain usecases
    and repositories that the consumer application needs.

    Attributes:
        text_processing: Text preprocessing use case
        analytics_usecase: Analytics use case
    """

    text_processing: object  # TextProcessing instance
    analytics_usecase: AnalyticsUseCase
    # TODO: Add more domain services as needed
    # notification_usecase: NotificationUseCase
    # report_usecase: ReportUseCase


class ConsumerRegistry:
    """Registry for consumer application domain services.

    This class provides centralized initialization of all domain services
    needed by the consumer application. Each application (consumer, api, worker)
    should have its own registry.

    Pattern inspired by Golang's term packages:
    - Each domain has a New() factory function
    - Logger is injected from Dependencies
    - Config is extracted from Dependencies
    - Services are initialized once and cached

    Example:
        deps = await init_dependencies(config)
        registry = ConsumerRegistry(deps)
        services = registry.initialize()

        # Use services in handlers
        output = services.text_processing.process(input_data)
        result = await services.analytics_usecase.process_analytics(data)
    """

    def __init__(self, deps: Dependencies):
        """Initialize registry with dependencies.

        Args:
            deps: Service dependencies container
        """
        self.deps = deps
        self.logger = deps.logger
        self.config = deps.config
        self._services: Optional[DomainServices] = None

    def initialize(self) -> DomainServices:
        """Initialize all domain services for consumer app.

        This method creates instances of all domain usecases and repositories
        with proper dependency injection. Services are cached after first initialization.

        Returns:
            DomainServices container with all initialized services

        Raises:
            Exception: If any service initialization fails
        """
        if self._services is not None:
            self.logger.debug("[ConsumerRegistry] Returning cached services")
            return self._services

        try:
            self.logger.info("[ConsumerRegistry] Initializing domain services...")

            # Initialize text preprocessing use case
            text_processing_config = TextProcessingConfig(
                min_text_length=self.config.preprocessor.min_text_length,
                max_comments=self.config.preprocessor.max_comments,
            )
            text_processing = NewTextProcessing(text_processing_config, self.logger)
            self.logger.info("[ConsumerRegistry] Text preprocessing initialized")

            # Initialize analytics use case
            analytics_usecase = AnalyticsUseCase(self.deps)
            self.logger.info("[ConsumerRegistry] Analytics use case initialized")

            # TODO: Initialize other domain services as needed
            # notification_config = NotificationConfig(...)
            # notification_usecase = NewNotification(notification_config, self.logger)

            # TODO: Initialize repositories if needed
            # analytics_repo = NewAnalyticsRepository(self.deps.db, self.logger)

            self._services = DomainServices(
                text_processing=text_processing,
                analytics_usecase=analytics_usecase,
            )

            self.logger.info(
                "[ConsumerRegistry] All domain services initialized successfully"
            )
            return self._services

        except Exception as e:
            self.logger.error(
                "[ConsumerRegistry] Failed to initialize domain services",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise

    def get_services(self) -> DomainServices:
        """Get initialized domain services.

        Returns:
            DomainServices container

        Raises:
            RuntimeError: If services not initialized yet
        """
        if self._services is None:
            raise RuntimeError(
                "Domain services not initialized. Call initialize() first."
            )
        return self._services

    def shutdown(self):
        """Cleanup domain services on shutdown.

        This method should be called when the application is shutting down
        to properly cleanup any resources held by domain services.
        """
        try:
            self.logger.info("[ConsumerRegistry] Shutting down domain services...")

            # TODO: Cleanup services if needed
            # if self._services:
            #     if hasattr(self._services.some_service, 'close'):
            #         self._services.some_service.close()

            self._services = None
            self.logger.info("[ConsumerRegistry] Domain services shutdown complete")

        except Exception as e:
            self.logger.error(
                "[ConsumerRegistry] Error during shutdown",
                extra={"error": str(e)},
            )


__all__ = ["ConsumerRegistry", "DomainServices"]
