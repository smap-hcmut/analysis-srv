import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from pkg.logger.logger import Logger
from internal.post_insight.interface import IPostInsightUseCase
from internal.post_insight.type import CreatePostInsightInput
from internal.post_insight.repository.postgre.helpers import _parse_datetime
from internal.builder.interface import IResultBuilderUseCase
from internal.builder.type import BuildInput
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.text_preprocessing.type import (
    Input as TPInput,
    ContentInput,
)
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.impact_calculation.interface import IImpactCalculationUseCase
from internal.impact_calculation.type import (
    Input as ICInput,
    AuthorInput,
    InteractionInput,
    SentimentInput,
)
from internal.model.uap import UAPRecord
from ..interface import IAnalyticsPublisher
from ..type import (
    Config,
    Input,
    Output,
    AnalyticsResult,
)
from ..constant import (
    PLATFORM_UNKNOWN,
    STATUS_SUCCESS,
    STATUS_ERROR,
)
from .helpers import (
    normalize_platform,
    add_uap_metadata,
    build_error_result,
)


class AnalyticsProcess:
    def __init__(
        self,
        config: Config,
        post_insight_usecase: IPostInsightUseCase,
        logger: Logger,
        preprocessor: Optional[ITextPreprocessingUseCase] = None,
        intent_classifier: Optional[IIntentClassificationUseCase] = None,
        keyword_extractor: Optional[IKeywordExtractionUseCase] = None,
        sentiment_analyzer: Optional[ISentimentAnalysisUseCase] = None,
        impact_calculator: Optional[IImpactCalculationUseCase] = None,
        result_builder: Optional[IResultBuilderUseCase] = None,
        analytics_publisher: Optional[IAnalyticsPublisher] = None,
    ):
        self.config = config
        self.post_insight_usecase = post_insight_usecase
        self.logger = logger
        self.preprocessor = preprocessor
        self.intent_classifier = intent_classifier
        self.keyword_extractor = keyword_extractor
        self.sentiment_analyzer = sentiment_analyzer
        self.impact_calculator = impact_calculator
        self.result_builder = result_builder
        self.analytics_publisher = analytics_publisher

    async def execute(self, input_data: Input) -> Output:
        start_time = time.perf_counter()

        uap = input_data.uap_record
        project_id = input_data.project_id

        source_id = uap.ingest.source.source_id if uap.ingest.source else None
        doc_id = uap.content.doc_id if uap.content else None

        self.logger.info(
            f"internal.analytics.usecase.process: Processing source_id={source_id}, doc_id={doc_id}"
        )

        try:
            # Run pipeline stages (extract data from UAP)
            result = self._run_pipeline(uap, project_id)

            # Calculate processing time
            processing_time_ms = int((time.perf_counter() - start_time) * 1000)
            result.processing_time_ms = processing_time_ms

            # Persist result (async)
            await self.post_insight_usecase.create(
                CreatePostInsightInput(
                    project_id=result.project_id or "",
                    source_id=result.source_id,
                    content_text=result.content_text,
                    published_at=result.published_at,
                    crawled_at=result.crawled_at,
                    platform=result.platform,
                    permalink=result.permalink,
                    author_id=result.author_id,
                    author_name=result.author_name,
                    author_username=result.author_username,
                    follower_count=result.follower_count,
                    author_is_verified=result.author_is_verified,
                    view_count=result.view_count,
                    like_count=result.like_count,
                    comment_count=result.comment_count,
                    share_count=result.share_count,
                    save_count=result.save_count,
                    hashtags=result.hashtags or [],
                    overall_sentiment=result.overall_sentiment,
                    overall_sentiment_score=result.overall_sentiment_score,
                    overall_confidence=result.overall_confidence,
                    aspects_breakdown=result.aspects_breakdown,
                    keywords=result.keywords,
                    risk_level=result.risk_level,
                    risk_factors=result.risk_factors,
                    primary_intent=result.primary_intent,
                    intent_confidence=result.intent_confidence,
                    is_spam=result.is_spam,
                    engagement_score=result.engagement_score,
                    virality_score=result.virality_score,
                    influence_score=result.influence_score,
                    impact_score=result.impact_score,
                    processing_time_ms=result.processing_time_ms,
                    model_version=result.model_version,
                    processing_status=result.processing_status,
                    analyzed_at=result.analyzed_at,
                )
            )

            # Build enriched output + publish to Kafka
            await self._publish_enriched(input_data, result)

            self.logger.info(
                f"internal.analytics.usecase.process: Completed source_id={source_id}, "
                f"status={result.processing_status}, elapsed_ms={processing_time_ms}"
            )

            return Output(
                result=result,
                processing_status=STATUS_SUCCESS,
            )

        except Exception as exc:
            self.logger.error(
                f"internal.analytics.usecase.process: Error processing source_id={source_id}: {exc}"
            )

            # Return error output
            return Output(
                result=build_error_result(uap, project_id, str(exc)),
                processing_status=STATUS_ERROR,
                error_message=str(exc),
            )

    async def _publish_enriched(
        self,
        input_data: Input,
        result: AnalyticsResult,
    ) -> None:
        if not self.result_builder or not self.analytics_publisher:
            return

        try:
            build_input = BuildInput(
                uap_record=input_data.uap_record,
                analytics_result=result,
            )
            build_output = self.result_builder.build(build_input)

            if build_output.success:
                await self.analytics_publisher.publish(build_output.enriched)
            else:
                self.logger.error(
                    f"internal.analytics.usecase.process: Build enriched failed: {build_output.error_message}"
                )

        except Exception as exc:
            # Non-fatal — log but don't fail the pipeline
            self.logger.error(f"internal.analytics.usecase.process: Publish enriched failed: {exc}")

    def _run_pipeline(
        self,
        uap: UAPRecord,
        project_id: str,
    ) -> AnalyticsResult:
        # Ingest block
        ingest = uap.ingest
        source_id = ingest.source.source_id if ingest.source else None
        source_type = ingest.source.source_type if ingest.source else PLATFORM_UNKNOWN
        platform = normalize_platform(source_type)

        # Content block
        content = uap.content
        text = content.text if content else ""
        published_at = _parse_datetime(content.published_at if content else None)

        # Author
        author = content.author if content else None
        author_followers = author.followers if author and author.followers else 0
        author_is_verified = (
            author.is_verified if author else False
        )

        # Signals block
        signals = uap.signals
        engagement = signals.engagement if signals else None

        views = engagement.view_count if engagement else 0
        likes = engagement.like_count if engagement else 0
        comments = engagement.comment_count if engagement else 0
        shares = engagement.share_count if engagement else 0
        saves = engagement.save_count if engagement else 0

        result = AnalyticsResult(
            id=str(uuid.uuid4()),
            project_id=project_id,
            source_id=source_id,
            platform=platform,
            published_at=published_at or datetime.now(timezone.utc),
            analyzed_at=datetime.now(timezone.utc),
            model_version=self.config.model_version,
        )

        # Add raw metrics
        result.view_count = views
        result.like_count = likes
        result.comment_count = comments
        result.share_count = shares
        result.save_count = saves
        result.follower_count = author_followers

        # Add UAP metadata
        add_uap_metadata(result, uap, self.config)

        # === STAGE 1: PREPROCESSING ===

        full_text = text

        if self.config.enable_preprocessing and self.preprocessor:
            try:
                # Prepare input for text preprocessing
                tp_input = TPInput(
                    content=ContentInput(
                        text=text,
                        transcription="",  # UAP doesn't have transcription in content
                    ),
                    comments=[],  # UAP doesn't have comments in content block
                )

                tp_output = self.preprocessor.process(tp_input)

                # Update result with spam detection info
                result.is_spam = tp_output.is_spam
                result.spam_reasons = tp_output.spam_reasons

                # Use clean text for subsequent stages
                full_text = tp_output.clean_text

                if result.is_spam:
                    # Mark risk as LOW for spam but flag it
                    result.risk_level = "LOW"
                    result.processing_status = "success_spam"

            except Exception as e:
                self.logger.error(f"internal.analytics.usecase.process: Preprocessing failed: {e}")

        # === STAGE 2: INTENT CLASSIFICATION ===

        if self.config.enable_intent_classification and self.intent_classifier:
            # TODO: Implement intent classification
            pass

        # === STAGE 3: KEYWORD EXTRACTION ===

        if self.config.enable_keyword_extraction and self.keyword_extractor:
            # TODO: Implement keyword extraction
            pass

        # === STAGE 4: SENTIMENT ANALYSIS ===

        if self.config.enable_sentiment_analysis and self.sentiment_analyzer:
            # TODO: Implement sentiment analysis
            pass

        # === STAGE 5: IMPACT CALCULATION ===

        if self.config.enable_impact_calculation and self.impact_calculator:
            try:
                # Prepare input for impact calculation
                # Check AuthorInput field names. In impact type it is strict.
                ic_input = ICInput(
                    interaction=InteractionInput(
                        views=views,
                        likes=likes,
                        comments_count=comments,
                        shares=shares,
                        saves=saves,
                    ),
                    author=AuthorInput(
                        followers=author_followers,
                        is_verified=author_is_verified,  # Already bool
                    ),
                    sentiment=SentimentInput(
                        label=result.overall_sentiment,
                        score=result.overall_sentiment_score,
                    ),
                    platform=platform,
                    text=full_text,  # Pass text for risk keyword matching
                )

                ic_output = self.impact_calculator.process(ic_input)

                # Update result with impact metrics
                result.impact_score = ic_output.impact_score
                result.risk_level = ic_output.risk_level
                result.is_viral = ic_output.is_viral
                result.is_kol = ic_output.is_kol
                result.engagement_score = ic_output.engagement_score
                result.virality_score = ic_output.virality_score
                result.influence_score = ic_output.influence_score
                result.risk_factors = ic_output.risk_factors

                # Map breakdown
                if ic_output.impact_breakdown:
                    result.impact_breakdown = {
                        "engagement_score": ic_output.impact_breakdown.engagement_score,
                        "reach_score": ic_output.impact_breakdown.reach_score,
                        "platform_multiplier": ic_output.impact_breakdown.platform_multiplier,
                        "sentiment_amplifier": ic_output.impact_breakdown.sentiment_amplifier,
                        "raw_impact": ic_output.impact_breakdown.raw_impact,
                    }

            except Exception as e:
                self.logger.error(f"internal.analytics.usecase.process: Impact calculation failed: {e}")

        return result
