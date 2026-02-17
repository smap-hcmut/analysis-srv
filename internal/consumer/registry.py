"""Domain registry for consumer application."""

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
from internal.impact_calculation import (
    New as NewImpactCalculation,
    Config as ImpactCalculationConfig,
)
from internal.analyzed_post import (
    NewAnalyzedPostUseCase,
)
from internal.analyzed_post.repository import (
    New as NewAnalyzedPostRepository,
)
from internal.analytics import (
    NewAnalyticsPipeline,
    NewAnalyticsHandler,
    Config as AnalyticsConfig,
)


@dataclass
class DomainServices:
    """Container for all domain services used by consumer app.

    Attributes:
        text_processing: Text preprocessing use case
        intent_classification: Intent classification use case
        keyword_extraction: Keyword extraction use case
        sentiment_analysis: Sentiment analysis use case
        impact_calculation: Impact calculation use case
        analyzed_post_usecase: Analyzed post CRUD use case
        analytics_handler: Analytics pipeline handler
    """

    text_processing: object  # TextProcessing instance
    intent_classification: object  # IntentClassification instance
    keyword_extraction: object  # KeywordExtraction instance
    sentiment_analysis: object  # SentimentAnalysis instance
    impact_calculation: object  # ImpactCalculation instance
    analyzed_post_usecase: object  # AnalyzedPostUseCase instance
    analytics_handler: object  # AnalyticsHandler instance


class ConsumerRegistry:
    """Registry for consumer application domain services.

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

            # Initialize impact calculation use case
            impact_calculation_config = ImpactCalculationConfig(
                weight_view=self.config.impact.weight.view,
                weight_like=self.config.impact.weight.like,
                weight_comment=self.config.impact.weight.comment,
                weight_save=self.config.impact.weight.save,
                weight_share=self.config.impact.weight.share,
                platform_weight_tiktok=self.config.impact.platform.tiktok,
                platform_weight_facebook=self.config.impact.platform.facebook,
                platform_weight_youtube=self.config.impact.platform.youtube,
                platform_weight_instagram=self.config.impact.platform.instagram,
                platform_weight_unknown=self.config.impact.platform.unknown,
                amp_negative=self.config.impact.amplifier.negative,
                amp_neutral=self.config.impact.amplifier.neutral,
                amp_positive=self.config.impact.amplifier.positive,
                viral_threshold=self.config.impact.threshold.viral,
                kol_follower_threshold=self.config.impact.threshold.kol_followers,
                max_raw_score_ceiling=self.config.impact.threshold.max_raw_score,
            )
            impact_calculation = NewImpactCalculation(
                impact_calculation_config, self.logger
            )
            self.logger.info("[ConsumerRegistry] Impact calculation initialized")

            # Initialize analyzed_post repository
            analyzed_post_repository = NewAnalyzedPostRepository(
                self.deps.db, self.logger
            )
            self.logger.info("[ConsumerRegistry] Analyzed post repository initialized")

            # Initialize analyzed_post use case
            analyzed_post_usecase = NewAnalyzedPostUseCase(
                repository=analyzed_post_repository,
                logger=self.logger,
            )
            self.logger.info("[ConsumerRegistry] Analyzed post use case initialized")

            # Initialize analytics pipeline
            analytics_config = AnalyticsConfig(
                model_version="1.0.0",
                enable_preprocessing=True,
                enable_intent_classification=True,
                enable_keyword_extraction=True,
                enable_sentiment_analysis=True,
                enable_impact_calculation=True,
            )
            analytics_pipeline = NewAnalyticsPipeline(
                config=analytics_config,
                analyzed_post_usecase=analyzed_post_usecase,
                logger=self.logger,
                preprocessor=text_processing,
                intent_classifier=intent_classification,
                keyword_extractor=keyword_extraction,
                sentiment_analyzer=sentiment_analysis,
                impact_calculator=impact_calculation,
            )
            self.logger.info("[ConsumerRegistry] Analytics pipeline initialized")

            # Initialize analytics handler
            analytics_handler = NewAnalyticsHandler(
                pipeline=analytics_pipeline,
                logger=self.logger,
            )
            self.logger.info("[ConsumerRegistry] Analytics handler initialized")

            self._services = DomainServices(
                text_processing=text_processing,
                intent_classification=intent_classification,
                keyword_extraction=keyword_extraction,
                sentiment_analysis=sentiment_analysis,
                impact_calculation=impact_calculation,
                analyzed_post_usecase=analyzed_post_usecase,
                analytics_handler=analytics_handler,
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
