"""Analytics Orchestrator - core business logic."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from pkg.logger.logger import Logger
from internal.analyzed_post.interface import IAnalyzedPostUseCase
from internal.analyzed_post.type import CreateAnalyzedPostInput
from ..interface import IAnalyticsPipeline
from ..type import (
    Config,
    Input,
    Output,
    PostData,
    EventMetadata,
    EnrichedPostData,
    AnalyticsResult,
)
from ..constant import (
    MODEL_VERSION,
    DEFAULT_EVENT_ID,
    DEFAULT_POST_ID,
    DEFAULT_PLATFORM,
    PIPELINE_VERSION_TEMPLATE,
    PIPELINE_VERSION_NUMBER,
    PLATFORM_UNKNOWN,
    STATUS_SUCCESS,
    STATUS_ERROR,
)


class AnalyticsPipeline(IAnalyticsPipeline):
    """Core business logic for analytics pipeline.

    This orchestrator coordinates the 5-stage pipeline and applies
    skip logic for spam/seeding/noise posts.
    """

    def __init__(
        self,
        config: Config,
        analyzed_post_usecase: IAnalyzedPostUseCase,
        logger: Optional[Logger] = None,
        *,
        preprocessor: Optional[Any] = None,
        intent_classifier: Optional[Any] = None,
        keyword_extractor: Optional[Any] = None,
        sentiment_analyzer: Optional[Any] = None,
        impact_calculator: Optional[Any] = None,
    ):
        """Initialize orchestrator with dependencies.

        Args:
            config: Pipeline configuration
            analyzed_post_usecase: Use case for persisting analyzed posts
            logger: Logger instance (optional)
            preprocessor: Text preprocessor (optional)
            intent_classifier: Intent classifier (optional)
            keyword_extractor: Keyword extractor (optional)
            sentiment_analyzer: Sentiment analyzer (optional)
            impact_calculator: Impact calculator (optional)
        """
        self.config = config
        self.analyzed_post_usecase = analyzed_post_usecase
        self.logger = logger

        # Optional AI modules (can be None if disabled)
        self.preprocessor = preprocessor
        self.intent_classifier = intent_classifier
        self.keyword_extractor = keyword_extractor
        self.sentiment_analyzer = sentiment_analyzer
        self.impact_calculator = impact_calculator

    async def process(self, input_data: Input) -> Output:
        """Process a single post through the analytics pipeline.

        Args:
            input_data: Input with post data and metadata

        Returns:
            Output with analytics result

        Raises:
            ValueError: If input is invalid
        """
        start_time = time.perf_counter()

        post_data = input_data.post_data
        event_metadata = input_data.event_metadata or {}
        project_id = input_data.project_id

        post_id = post_data.meta.get("id")

        if self.logger:
            self.logger.info(f"[AnalyticsPipeline] Processing post_id={post_id}")

        try:
            # Enrich post data with event metadata
            enriched_post = self._enrich_post_data(
                post_data, event_metadata, project_id
            )

            # Run pipeline stages
            result = self._run_pipeline(enriched_post)

            # Calculate processing time
            processing_time_ms = int((time.perf_counter() - start_time) * 1000)
            result.processing_time_ms = processing_time_ms

            # Persist result (async)
            await self.analyzed_post_usecase.create(
                CreateAnalyzedPostInput(data=result.to_dict())
            )

            if self.logger:
                self.logger.info(
                    f"[AnalyticsPipeline] Completed post_id={post_id}, "
                    f"status={result.processing_status}, elapsed_ms={processing_time_ms}"
                )

            return Output(
                result=result,
                processing_status=STATUS_SUCCESS,
            )

        except Exception as exc:
            if self.logger:
                self.logger.error(
                    f"[AnalyticsPipeline] Error processing post_id={post_id}: {exc}"
                )

            # Return error output
            return Output(
                result=self._build_error_result(post_data, str(exc)),
                processing_status=STATUS_ERROR,
                error_message=str(exc),
            )

    def _enrich_post_data(
        self,
        post_data: PostData,
        event_metadata: Optional[EventMetadata],
        project_id: Optional[str],
    ) -> EnrichedPostData:
        """Enrich post data with event metadata."""
        meta = post_data.meta.copy()
        meta["project_id"] = project_id

        if event_metadata:
            meta["job_id"] = event_metadata.job_id
            meta["batch_index"] = event_metadata.batch_index
            meta["task_type"] = event_metadata.task_type
            meta["keyword_source"] = event_metadata.keyword
            meta["brand_name"] = event_metadata.brand_name
            meta["keyword"] = event_metadata.keyword

            if event_metadata.timestamp:
                try:
                    meta["crawled_at"] = datetime.fromisoformat(
                        event_metadata.timestamp.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    meta["crawled_at"] = None

            platform = meta.get("platform", event_metadata.platform or DEFAULT_PLATFORM)
        else:
            platform = meta.get("platform", DEFAULT_PLATFORM)

        meta["pipeline_version"] = PIPELINE_VERSION_TEMPLATE.format(
            platform=platform.lower(), version=PIPELINE_VERSION_NUMBER
        )

        return EnrichedPostData(
            meta=meta,
            content=post_data.content,
            interaction=post_data.interaction,
            author=post_data.author,
            comments=post_data.comments,
        )

    def _run_pipeline(self, enriched_post_data: EnrichedPostData) -> AnalyticsResult:
        """Run the full analytics pipeline."""
        meta = enriched_post_data.meta
        content = enriched_post_data.content
        interaction = enriched_post_data.interaction
        author = enriched_post_data.author

        post_id = meta.get("id")
        platform = self._normalize_platform(meta.get("platform"))

        # Extract text for analysis
        text = content.get("text") or content.get("description") or ""
        transcription = content.get("transcription") or ""
        full_text = f"{text} {transcription}".strip()

        # Initialize result with base data
        result = AnalyticsResult(
            id=post_id,
            project_id=meta.get("project_id"),
            platform=platform,
            published_at=meta.get("published_at") or datetime.now(timezone.utc),
            analyzed_at=datetime.now(timezone.utc),
            model_version=self.config.model_version,
        )

        # Add raw metrics
        result.view_count = self._safe_int(interaction.get("views"))
        result.like_count = self._safe_int(interaction.get("likes"))
        result.comment_count = self._safe_int(interaction.get("comments_count"))
        result.share_count = self._safe_int(interaction.get("shares"))
        result.save_count = self._safe_int(interaction.get("saves"))
        result.follower_count = self._safe_int(author.get("followers"))

        # Add crawler metadata
        self._add_crawler_metadata(result, meta, content, author)

        # Stage 1: Preprocessing (if enabled)
        if self.config.enable_preprocessing and self.preprocessor:
            # TODO: Implement preprocessing
            pass

        # Stage 2: Intent classification (if enabled)
        if self.config.enable_intent_classification and self.intent_classifier:
            # TODO: Implement intent classification
            # Check if should skip (spam/seeding)
            pass

        # Stage 3: Keyword extraction (if enabled)
        keywords = []
        if self.config.enable_keyword_extraction and self.keyword_extractor:
            # TODO: Implement keyword extraction
            pass

        # Stage 4: Sentiment analysis (if enabled)
        if self.config.enable_sentiment_analysis and self.sentiment_analyzer:
            # TODO: Implement sentiment analysis
            pass

        # Stage 5: Impact calculation (if enabled)
        if self.config.enable_impact_calculation and self.impact_calculator:
            # TODO: Implement impact calculation
            pass

        return result

    def _add_crawler_metadata(
        self,
        result: AnalyticsResult,
        meta: dict[str, Any],
        content: dict[str, Any],
        author: dict[str, Any],
    ) -> None:
        """Add crawler metadata to result.

        Args:
            result: AnalyticsResult to update
            meta: Post metadata
            content: Post content
            author: Author data
        """
        # Batch context
        result.job_id = meta.get("job_id")
        result.batch_index = meta.get("batch_index")
        result.task_type = meta.get("task_type")
        result.keyword_source = meta.get("keyword_source")
        result.crawled_at = meta.get("crawled_at")
        result.pipeline_version = meta.get("pipeline_version")

        # Brand/Keyword
        result.brand_name = meta.get("brand_name")
        result.keyword = meta.get("keyword")

        # Content fields
        result.content_text = content.get("text")
        result.content_transcription = content.get("transcription")
        result.media_duration = content.get("duration")
        result.hashtags = content.get("hashtags")
        result.permalink = meta.get("permalink")

        # Author fields
        result.author_id = author.get("id")
        result.author_name = author.get("name")
        result.author_username = author.get("username")
        result.author_avatar_url = author.get("avatar_url")
        result.author_is_verified = author.get("is_verified", False)

    def _build_error_result(
        self,
        post_data: PostData,
        error_message: str,
    ) -> AnalyticsResult:
        """Build minimal result for error cases."""
        meta = post_data.meta

        return AnalyticsResult(
            id=meta.get("id", DEFAULT_POST_ID),
            project_id=meta.get("project_id"),
            platform=self._normalize_platform(meta.get("platform")),
            analyzed_at=datetime.now(timezone.utc),
            processing_status=STATUS_ERROR,
        )

    @staticmethod
    def _normalize_platform(platform: Optional[str]) -> str:
        """Normalize platform name to uppercase."""
        if not platform:
            return PLATFORM_UNKNOWN
        return str(platform).strip().upper()

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Safely convert value to int."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


__all__ = ["AnalyticsPipeline"]
