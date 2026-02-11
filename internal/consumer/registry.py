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
from internal.intent_classification import (
    New as NewIntentClassification,
    Config as IntentClassificationConfig,
)
from internal.keyword_extraction import (
    New as NewKeywordExtraction,
    Config as KeywordExtractionConfig,
)
from internal.sentiment_analysis import (
    New as NewSentimentAnalysis,
    Config as SentimentAnalysisConfig,
)
from internal.analytics.usecase import AnalyticsUseCase


@dataclass
class DomainServices:
    """Container for all domain services used by consumer app.

    This struct holds initialized instances of all domain usecases
    and repositories that the consumer application needs.

    Attributes:
        text_processing: Text preprocessing use case
        intent_classification: Intent classification use case
        keyword_extraction: Keyword extraction use case
        sentiment_analysis: Sentiment analysis use case
        analytics_usecase: Analytics use case
    """

    text_processing: object  # TextProcessing instance
    intent_classification: object  # IntentClassification instance
    keyword_extraction: object  # KeywordExtraction instance
    sentiment_analysis: object  # SentimentAnalysis instance
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
        text_output = services.text_processing.process(text_input)
        intent_output = services.intent_classification.process(intent_input)
        keyword_output = services.keyword_extraction.process(keyword_input)
        sentiment_output = services.sentiment_analysis.process(sentiment_input)
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

            # Initialize intent classification use case
            intent_classification_config = IntentClassificationConfig(
                patterns_path=self.config.intent_classifier.patterns_path,
                confidence_threshold=self.config.intent_classifier.confidence_threshold,
            )
            intent_classification = NewIntentClassification(
                intent_classification_config, self.logger
            )
            self.logger.info("[ConsumerRegistry] Intent classification initialized")

            # Initialize keyword extraction use case
            keyword_extraction_config = KeywordExtractionConfig(
                aspect_dictionary_path=self.config.aspect_mapping.dictionary_path,
                enable_ai=True,
                ai_threshold=5,
                max_keywords=self.config.keyword_extraction.max_keywords,
            )
            keyword_extraction = NewKeywordExtraction(
                keyword_extraction_config,
                self.deps.keyword_extractor,  # Inject SpacyYake from Dependencies
                self.logger,
            )
            self.logger.info("[ConsumerRegistry] Keyword extraction initialized")

            # Initialize sentiment analysis use case
            sentiment_analysis_config = SentimentAnalysisConfig(
                context_window_size=100,
                threshold_positive=0.25,
                threshold_negative=-0.25,
            )
            sentiment_analysis = NewSentimentAnalysis(
                sentiment_analysis_config,
                self.deps.sentiment,  # Inject PhoBERTONNX from Dependencies
                self.logger,
            )
            self.logger.info("[ConsumerRegistry] Sentiment analysis initialized")

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
                intent_classification=intent_classification,
                keyword_extraction=keyword_extraction,
                sentiment_analysis=sentiment_analysis,
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
