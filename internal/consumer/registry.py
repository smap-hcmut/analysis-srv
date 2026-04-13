from dataclasses import dataclass
from typing import Optional

from internal.consumer.type import Dependencies
from internal.domain.loader import DomainLoader
from internal.domain.type import DomainRegistry
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
)
from internal.analytics.type import Config as AnalyticsConfig
from internal.analytics.usecase.batch_enricher import NLPBatchEnricher
from internal.contract_publisher.usecase.new import New as NewContractPublisher
from internal.contract_publisher.type import ContractPublishConfig
from internal.normalization.usecase.new import New as NewNormalization
from internal.dedup.usecase.new import New as NewDedup
from internal.spam.usecase.new import New as NewSpam
from internal.threads.usecase.new import New as NewThreads
from internal.ingestion.usecase.new import New as NewIngestion
from internal.pipeline.type import PipelineConfig, PipelineServices
from internal.pipeline.usecase.new import New as NewPipeline
from internal.ontology.usecase.file_registry import FileOntologyRegistry
from internal.enrichment.usecase.usecase import EnrichmentUseCase
from internal.enrichment.type import EnricherConfig


@dataclass
class DomainServices:
    """Resolved domain services — kept for registry interface compatibility."""

    post_insight_usecase: object
    nlp_batch_enricher: object


class ConsumerRegistry:
    def __init__(self, deps: Dependencies):
        self.deps = deps
        self.logger = deps.logger
        self.config = deps.config
        self._services: Optional[DomainServices] = None

        # Pipeline references (set during initialize())
        self.pipeline_usecase = None
        self.pipeline_config = None
        self.ingestion_usecase = None
        self.contract_publisher = None
        self.post_insight_usecase = None
        self.domain_registry: Optional[DomainRegistry] = None

    def initialize(self) -> DomainServices:
        if self._services is not None:
            self.logger.debug("Returning cached services")
            return self._services

        try:
            # ------------------------------------------------------------------
            # NLP services (shared between NLPBatchEnricher and future stages)
            # ------------------------------------------------------------------
            text_processing_usecase = NewTextPreprocessingUseCase(
                config=TextProcessingConfig(
                    min_text_length=self.config.preprocessor.min_text_length,
                    max_comments=self.config.preprocessor.max_comments,
                ),
                logger=self.logger,
            )
            self.logger.info("Text preprocessing use case initialized")

            intent_classification_usecase = NewIntentClassification(
                config=IntentClassificationConfig(
                    patterns_path=self.config.intent_classifier.patterns_path,
                    confidence_threshold=self.config.intent_classifier.confidence_threshold,
                ),
                logger=self.logger,
            )
            self.logger.info("Intent classification use case initialized")

            keyword_extraction_usecase = NewKeywordExtractionUseCase(
                config=KeywordExtractionConfig(
                    aspect_dictionary_path=self.config.keyword_extraction.aspect_dictionary_path,
                    enable_ai=self.config.keyword_extraction.enable_ai,
                    ai_threshold=self.config.keyword_extraction.ai_threshold,
                    max_keywords=self.config.keyword_extraction.max_keywords,
                ),
                ai_extractor=self.deps.keyword_extractor,
                logger=self.logger,
            )
            self.logger.info("Keyword extraction use case initialized")

            sentiment_analysis_usecase = NewSentimentAnalysisUseCase(
                config=SentimentAnalysisConfig(
                    context_window_size=self.config.sentiment_analysis.context_window_size,
                    threshold_positive=self.config.sentiment_analysis.threshold_positive,
                    threshold_negative=self.config.sentiment_analysis.threshold_negative,
                ),
                phobert_model=self.deps.sentiment,
                logger=self.logger,
            )
            self.logger.info("Sentiment analysis use case initialized")

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
            self.logger.info("Impact calculation use case initialized")

            # ------------------------------------------------------------------
            # Persistence — post_insight
            # ------------------------------------------------------------------
            post_insight_repository = NewPostInsightRepository(
                db=self.deps.db,
                logger=self.logger,
            )
            self.logger.info("PostInsightRepository initialized")

            post_insight_usecase = NewPostInsightUseCase(
                repository=post_insight_repository,
                logger=self.logger,
            )
            self.post_insight_usecase = post_insight_usecase
            self.logger.info("PostInsightUsecase initialized")

            # ------------------------------------------------------------------
            # Result builder (UAPRecord + AnalyticsResult → InsightMessage)
            # ------------------------------------------------------------------
            result_builder = NewResultBuilder(logger=self.logger)
            self.logger.info("Result Builder initialized")

            # ------------------------------------------------------------------
            # Contract publisher (3 knowledge-srv topics)
            # ------------------------------------------------------------------
            contract_publisher = NewContractPublisher(
                kafka_producer=self.deps.kafka_producer,
                config=ContractPublishConfig(
                    batch_size=self.config.contract_publisher.batch_size,
                    domain_overlay=self.config.contract_publisher.domain_overlay,
                ),
                logger=self.logger,
            )
            self.contract_publisher = contract_publisher
            self.logger.info("Contract Publisher initialized")

            # ------------------------------------------------------------------
            # NLPBatchEnricher — replaces legacy AnalyticsProcess
            # ------------------------------------------------------------------
            nlp_batch_enricher = NLPBatchEnricher(
                config=AnalyticsConfig(
                    model_version=self.config.nlp.model_version,
                    enable_preprocessing=self.config.nlp.enable_preprocessing,
                    enable_intent_classification=self.config.nlp.enable_intent_classification,
                    enable_keyword_extraction=self.config.nlp.enable_keyword_extraction,
                    enable_sentiment_analysis=self.config.nlp.enable_sentiment_analysis,
                    enable_impact_calculation=self.config.nlp.enable_impact_calculation,
                ),
                logger=self.logger,
                preprocessor=text_processing_usecase,
                intent_classifier=intent_classification_usecase,
                keyword_extractor=keyword_extraction_usecase,
                sentiment_analyzer=sentiment_analysis_usecase,
                impact_calculator=impact_calculation_usecase,
                result_builder=result_builder,
            )
            self.logger.info("NLPBatchEnricher initialized")

            # ------------------------------------------------------------------
            # Ontology registry (YAML-backed, VinFast domain)
            # ------------------------------------------------------------------
            ontology_registry = FileOntologyRegistry.from_config(self.config.ontology)
            self.logger.info(
                "Ontology registry initialized",
                extra={
                    "entities": len(ontology_registry.entities),
                    "taxonomy_nodes": len(ontology_registry.taxonomy_nodes),
                    "source_channels": len(ontology_registry.source_channels),
                },
            )

            # ------------------------------------------------------------------
            # Domain registry (per-domain YAML configs for routing + ontology)
            # ------------------------------------------------------------------
            domain_registry = DomainLoader.load_from_dir(
                domains_dir=self.config.domain_registry.domains_dir,
                fallback_code=self.config.domain_registry.fallback_domain,
            )
            self.domain_registry = domain_registry
            self.logger.info(
                "Domain registry initialized",
                extra={"domains": domain_registry.domain_codes()},
            )

            # ------------------------------------------------------------------
            # Phase 3 pipeline stages
            # ------------------------------------------------------------------
            normalization_uc = NewNormalization()
            self.logger.info("Normalization usecase initialized")

            dedup_uc = NewDedup()
            self.logger.info("Dedup usecase initialized")

            spam_uc = NewSpam()
            self.logger.info("Spam usecase initialized")

            threads_uc = NewThreads()
            self.logger.info("Threads usecase initialized")

            # ------------------------------------------------------------------
            # Phase 4: Enrichment usecase (entity + semantic + topic)
            # ------------------------------------------------------------------
            enricher_config = EnricherConfig(
                entity_enabled=self.config.enrichment.entity_enabled,
                semantic_enabled=self.config.enrichment.semantic_enabled,
                topic_enabled=self.config.enrichment.topic_enabled,
                source_influence_enabled=self.config.enrichment.source_influence_enabled,
                semantic_full_enabled=self.config.enrichment.semantic_full_enabled,
            )
            enrichment_uc = EnrichmentUseCase(
                config=enricher_config,
                ontology_registry=ontology_registry,
            )
            self.logger.info("Enrichment usecase initialized")

            pipeline_services = PipelineServices(
                normalization=normalization_uc,
                dedup=dedup_uc,
                spam=spam_uc,
                threads=threads_uc,
                nlp_enricher=nlp_batch_enricher,
                ontology_registry=ontology_registry,
                enrichment=enrichment_uc,
            )
            pipeline_config = PipelineConfig(
                enable_normalization=self.config.pipeline.enable_normalization,
                enable_dedup=self.config.pipeline.enable_dedup,
                enable_spam=self.config.pipeline.enable_spam,
                enable_threads=self.config.pipeline.enable_threads,
                enable_nlp=self.config.pipeline.enable_nlp,
                enable_enrichment=self.config.pipeline.enable_enrichment,
                enable_review=self.config.pipeline.enable_review,
                enable_reporting=self.config.pipeline.enable_reporting,
                enable_crisis=self.config.pipeline.enable_crisis,
                services=pipeline_services,
            )
            self.pipeline_usecase = NewPipeline(logger=self.logger)
            self.pipeline_config = pipeline_config
            self.logger.info("Pipeline usecase (Phase 3 + NLP) initialized")

            # ------------------------------------------------------------------
            # Ingestion usecase (raw UAPRecords → IngestedBatchBundle)
            # ------------------------------------------------------------------
            self.ingestion_usecase = NewIngestion(logger=self.logger)
            self.logger.info("Ingestion usecase initialized")

            self._services = DomainServices(
                post_insight_usecase=post_insight_usecase,
                nlp_batch_enricher=nlp_batch_enricher,
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

            # Flush contract publisher on shutdown
            if self.contract_publisher:
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.contract_publisher.close())
                    else:
                        loop.run_until_complete(self.contract_publisher.close())
                except Exception as e:
                    self.logger.error(f"Error closing contract publisher: {e}")

            self._services = None
            self.logger.info("Domain services shutdown complete")

        except Exception as e:
            self.logger.error(
                "Error during shutdown",
                extra={"error": str(e)},
            )


__all__ = ["ConsumerRegistry", "DomainServices"]
