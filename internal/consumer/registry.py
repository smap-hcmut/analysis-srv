from dataclasses import dataclass
from typing import Optional

from internal.consumer.type import Dependencies
from internal.text_preprocessing import (
    NewTextPreprocessingUseCase,
    Config as TextProcessingConfig,
)
from internal.intent_classification import (
    NewIntentClassificationUseCase as NewIntentClassification,
    Config as IntentClassificationConfig,
)
from internal.keyword_extraction import (
    NewKeywordExtractionUseCase,
    Config as KeywordExtractionConfig,
)
from internal.sentiment_analysis import (
    NewSentimentAnalysisUseCase,
    Config as SentimentAnalysisConfig,
)
from internal.impact_calculation import (
    NewImpactCalculationUseCase as NewImpactCalculation,
    Config as ImpactCalculationConfig,
)
from internal.post_insight import (
    NewPostInsightUseCase,
)
from internal.post_insight.repository import (
    New as NewPostInsightRepository,
)
from internal.builder import (
    NewResultBuilderUseCase as NewResultBuilder,
    IResultBuilderUseCase,
)
from internal.analytics import (
    NewAnalyticsPipeline,
    Config as AnalyticsConfig,
    IAnalyticsUseCase,
)
from internal.analytics.delivery.kafka.producer.new import New as NewAnalyticsPublisher
from internal.analytics.delivery.kafka.producer.type import PublishConfig
from internal.analytics.delivery.kafka.consumer.new import (
    new_kafka_handler as NewAnalyticsHandler,
)


@dataclass
class DomainServices:
    text_processing_usecase: object  # TextProcessing instance
    intent_classification_usecase: object  # IntentClassification instance
    keyword_extraction_usecase: object  # KeywordExtraction instance
    sentiment_analysis_usecase: object  # SentimentAnalysis instance
    impact_calculation_usecase: object  # ImpactCalculation instance
    post_insight_usecase: object  # PostInsightUseCase instance
    analytics_handler: object  # AnalyticsHandler instance


class ConsumerRegistry:
    def __init__(self, deps: Dependencies):
        self.deps = deps
        self.logger = deps.logger
        self.config = deps.config
        self._services: Optional[DomainServices] = None

    def initialize(self) -> DomainServices:
        if self._services is not None:
            self.logger.debug("Returning cached services")
            return self._services

        try:
            # Initialize text preprocessing use case
            text_processing_usecase = NewTextPreprocessingUseCase(
                config=TextProcessingConfig(
                    min_text_length=self.config.preprocessor.min_text_length,
                    max_comments=self.config.preprocessor.max_comments,
                ),
                logger=self.logger,
            )
            self.logger.info("Text preprocessing Use case initialized")

            # Initialize intent classification use case
            intent_classification_usecase = NewIntentClassification(
                config=IntentClassificationConfig(
                    patterns_path=self.config.intent_classifier.patterns_path,
                    confidence_threshold=self.config.intent_classifier.confidence_threshold,
                ),
                logger=self.logger,
            )
            self.logger.info("Intent classification Use case initialized")

            # Initialize keyword extraction use case
            keyword_extraction_usecase = NewKeywordExtractionUseCase(
                config=KeywordExtractionConfig(
                    aspect_dictionary_path="config/aspects_patterns.yaml",
                    enable_ai=True,
                    ai_threshold=5,
                    max_keywords=30,
                ),
                ai_extractor=self.deps.keyword_extractor,  # Inject SpacyYake from Dependencies
                logger=self.logger,
            )
            self.logger.info("Keyword extraction Use case initialized")

            # Initialize sentiment analysis use case
            sentiment_analysis_usecase = NewSentimentAnalysisUseCase(
                config=SentimentAnalysisConfig(
                    context_window_size=100,
                    threshold_positive=0.25,
                    threshold_negative=-0.25,
                ),
                phobert_model=self.deps.sentiment,
                logger=self.logger,
            )
            self.logger.info("Sentiment analysis Use case initialized")

            # Initialize impact calculation use case
            impact_calculation_usecase = NewImpactCalculation(
                config=ImpactCalculationConfig(
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
                ),
                logger=self.logger,
            )
            self.logger.info("Impact calculation Use case initialized")

            # Initialize post_insight repository
            post_insight_repository = NewPostInsightRepository(
                db=self.deps.db,
                logger=self.logger,
            )
            self.logger.info("PostInsightRepository initialized")

            # Initialize post_insight usecase
            post_insight_usecase = NewPostInsightUseCase(
                repository=post_insight_repository,
                logger=self.logger,
            )
            self.logger.info("PostInsightUsecase initialized")

            # Initialize result builder
            result_builder = NewResultBuilder(logger=self.logger)
            self.result_builder = result_builder
            self.logger.info("Result Builder initialized")

            # Initialize analytics publisher (Kafka output)
            analytics_publisher = NewAnalyticsPublisher(
                kafka_producer=self.deps.kafka_producer,
                config=PublishConfig(
                    topic="smap.analytics.output",
                    batch_size=10,
                    enabled=True,
                ),
                logger=self.logger,
            )
            self.logger.info("Analytics Publisher initialized")

            # Initialize analytics pipeline
            self.analytics_pipeline = NewAnalyticsPipeline(
                config=AnalyticsConfig(
                    model_version="1.0.0",
                    enable_preprocessing=True,
                    enable_intent_classification=True,
                    enable_keyword_extraction=True,
                    enable_sentiment_analysis=True,
                    enable_impact_calculation=True,
                ),
                post_insight_usecase=post_insight_usecase,
                logger=self.logger,
                preprocessor=text_processing_usecase,
                intent_classifier=intent_classification_usecase,
                keyword_extractor=keyword_extraction_usecase,
                sentiment_analyzer=sentiment_analysis_usecase,
                impact_calculator=impact_calculation_usecase,
                result_builder=self.result_builder,
                analytics_publisher=analytics_publisher,
            )
            self.logger.info("Analytics Pipeline Use case initialized")

            # Initialize analytics handler
            analytics_handler = NewAnalyticsHandler(
                pipeline=self.analytics_pipeline,
                logger=self.logger,
            )
            self.logger.info("Analytics Handler initialized")

            self._services = DomainServices(
                text_processing_usecase=text_processing_usecase,
                intent_classification_usecase=intent_classification_usecase,
                keyword_extraction_usecase=keyword_extraction_usecase,
                sentiment_analysis_usecase=sentiment_analysis_usecase,
                impact_calculation_usecase=impact_calculation_usecase,
                post_insight_usecase=post_insight_usecase,
                analytics_handler=analytics_handler,
            )

            return self._services

        except Exception as e:
            self.logger.error(
                "Failed to initialize domain services",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise

    def get_services(self) -> DomainServices:
        if self._services is None:
            raise RuntimeError(
                "Domain services not initialized. Call initialize() first."
            )
        return self._services

    def shutdown(self):
        try:
            self.logger.info("Shutting down domain services...")

            # TODO: Cleanup services if needed
            # if self._services:
            #     if hasattr(self._services.some_service, 'close'):
            #         self._services.some_service.close()

            self._services = None
            self.logger.info("Domain services shutdown complete")

        except Exception as e:
            self.logger.error(
                "Error during shutdown",
                extra={"error": str(e)},
            )


__all__ = ["ConsumerRegistry", "DomainServices"]
