"""NLPBatchEnricher — sync NLP enrichment for Phase 3-6 pipeline integration.

Replaces the legacy AnalyticsProcess by providing a batch-oriented sync
API that the pipeline's STAGE_NLP stage calls from asyncio.to_thread().

No async dependencies here — only pure sync NLP stages so the method can
safely be invoked inside a thread-pool executor.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from pkg.logger.logger import Logger
from internal.model.uap import UAPRecord
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.text_preprocessing.type import Input as TPInput, ContentInput
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.intent_classification.type import Input as IntentClassificationInput
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.keyword_extraction.type import Input as KeywordExtractionInput
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.sentiment_analysis.type import Input as SAInput, KeywordInput
from internal.impact_calculation.interface import IImpactCalculationUseCase
from internal.impact_calculation.type import (
    Input as ICInput,
    AuthorInput,
    InteractionInput,
    SentimentInput,
)
from internal.builder.interface import IResultBuilderUseCase
from internal.builder.type import BuildInput
from internal.pipeline.type import NLPFact
from internal.post_insight.type import CreatePostInsightInput
from internal.post_insight.repository.postgre.helpers import _parse_datetime

from ..type import Config, AnalyticsResult
from ..constant import PLATFORM_UNKNOWN
from .helpers import normalize_platform, add_uap_metadata, build_error_result


class NLPBatchEnricher:
    """Synchronous NLP enricher for a batch of UAPRecords.

    Runs all NLP stages (text preprocessing, intent classification, keyword
    extraction, sentiment analysis, impact calculation) on each UAPRecord and
    returns a list of NLPFact objects that carry both the enriched
    InsightMessage (for ContractPublisher) and the AnalyticsResult (for
    post_insight persistence).

    enrich_batch() runs in three phases to maximise ONNX throughput:
      Phase 1 (per record, fast): preprocessing → intent classification
                                  → keyword extraction
      Phase 2 (batched, one ONNX call):  sentiment analysis for all records
      Phase 3 (per record, fast): impact calculation → result builder

    Designed to be called via asyncio.to_thread() inside the STAGE_NLP step
    of the Phase 3-6 pipeline.
    """

    def __init__(
        self,
        config: Config,
        logger: Logger,
        preprocessor: Optional[ITextPreprocessingUseCase] = None,
        intent_classifier: Optional[IIntentClassificationUseCase] = None,
        keyword_extractor: Optional[IKeywordExtractionUseCase] = None,
        sentiment_analyzer: Optional[ISentimentAnalysisUseCase] = None,
        impact_calculator: Optional[IImpactCalculationUseCase] = None,
        result_builder: Optional[IResultBuilderUseCase] = None,
    ):
        self.config = config
        self.logger = logger
        self.preprocessor = preprocessor
        self.intent_classifier = intent_classifier
        self.keyword_extractor = keyword_extractor
        self.sentiment_analyzer = sentiment_analyzer
        self.impact_calculator = impact_calculator
        self.result_builder = result_builder

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich_batch(
        self,
        records: list[UAPRecord],
        project_id: str,
    ) -> list[NLPFact]:
        """Run NLP enrichment on a batch of UAPRecords.

        Three-phase execution to batch sentiment ONNX calls:
          Phase 1: stages 1-3 per record  (preprocessing / intent / keywords)
          Phase 2: batch sentiment analysis across all non-skipped records
          Phase 3: impact calculation + result builder per record

        Errors per record are logged and skipped — never raised.
        Returns one NLPFact per successfully enriched record.
        """
        if not records:
            return []

        # ----------------------------------------------------------------
        # Phase 1: stages 1-3 per record (fast Python, no ONNX)
        # ----------------------------------------------------------------
        # Each slot: (uap, result, full_text, kws_for_sa, skip, t_start) | None
        phase1: list = [None] * len(records)

        for idx, uap in enumerate(records):
            try:
                start = time.perf_counter()
                result, full_text, kws, skip = self._run_stages_1_to_3(uap, project_id)
                phase1[idx] = (uap, result, full_text, kws, skip, start)
            except Exception as exc:
                self.logger.error(
                    "internal.analytics.usecase.batch_enricher: "
                    f"stages 1-3 failed: {exc}"
                )

        # ----------------------------------------------------------------
        # Phase 2: batch sentiment analysis (1-2 ONNX calls total)
        # ----------------------------------------------------------------
        sa_indices: list[int] = []
        sa_inputs: list[SAInput] = []

        for idx, item in enumerate(phase1):
            if item is None:
                continue
            uap, result, full_text, kws, skip, _ = item
            if skip:
                continue
            if not self.config.enable_sentiment_analysis or not self.sentiment_analyzer:
                continue

            keyword_inputs = [
                KeywordInput(
                    keyword=kw.keyword,
                    aspect=kw.aspect,
                    position=None,
                    score=kw.score,
                    source=kw.source,
                )
                for kw in kws
            ]
            sa_inputs.append(SAInput(text=full_text, keywords=keyword_inputs))
            sa_indices.append(idx)

        # Call process_batch() — one ONNX call for all overall texts,
        # one more for all keyword context windows.
        sa_outputs_map: dict[int, object] = {}
        if sa_inputs and self.sentiment_analyzer:
            try:
                sa_outputs = self.sentiment_analyzer.process_batch(sa_inputs)
                for orig_idx, sa_out in zip(sa_indices, sa_outputs):
                    sa_outputs_map[orig_idx] = sa_out
            except Exception as exc:
                self.logger.error(
                    "internal.analytics.usecase.batch_enricher: "
                    f"batch sentiment analysis failed: {exc}"
                )

        # ----------------------------------------------------------------
        # Phase 3: apply sentiment + impact calculation + build NLPFact
        # ----------------------------------------------------------------
        facts: list[NLPFact] = []

        for idx, item in enumerate(phase1):
            if item is None:
                continue
            uap, result, full_text, kws, skip, start = item
            try:
                # Apply pre-computed sentiment result if available
                if idx in sa_outputs_map:
                    self._apply_sentiment_result(result, sa_outputs_map[idx])

                # Stage 5: impact calculation (fast, no ONNX)
                if (
                    not skip
                    and self.config.enable_impact_calculation
                    and self.impact_calculator
                ):
                    self._run_impact_calculation(uap, result, full_text)

                result.processing_time_ms = int((time.perf_counter() - start) * 1000)

                # Build NLPFact via result builder
                if self.result_builder:
                    build_output = self.result_builder.build(
                        BuildInput(uap_record=uap, analytics_result=result)
                    )
                    if build_output.success:
                        facts.append(
                            NLPFact(
                                uap_id=uap.content.doc_id if uap.content else "",
                                insight_message=build_output.enriched,
                                uap_record=uap,
                                analytics_result=result,
                            )
                        )
                    else:
                        self.logger.error(
                            "internal.analytics.usecase.batch_enricher: "
                            f"result builder failed: {build_output.error_message}"
                        )
            except Exception as exc:
                self.logger.error(
                    "internal.analytics.usecase.batch_enricher: "
                    f"phase 3 failed for record: {exc}"
                )

        return facts

    # ------------------------------------------------------------------
    # Helper: map NLPFact → CreatePostInsightInput (async callers use this)
    # ------------------------------------------------------------------

    @staticmethod
    def to_post_insight_input(fact: NLPFact) -> CreatePostInsightInput:
        """Convert an NLPFact to a CreatePostInsightInput for persistence."""
        r = fact.analytics_result
        if r is None:
            raise ValueError(
                "NLPFact.analytics_result is None — cannot build post_insight input"
            )
        return CreatePostInsightInput(
            project_id=r.project_id or "",
            source_id=r.source_id,
            content_text=r.content_text,
            published_at=r.published_at,
            crawled_at=r.crawled_at,
            platform=r.platform,
            permalink=r.permalink,
            author_id=r.author_id,
            author_name=r.author_name,
            author_username=r.author_username,
            follower_count=r.follower_count,
            author_is_verified=r.author_is_verified,
            view_count=r.view_count,
            like_count=r.like_count,
            comment_count=r.comment_count,
            share_count=r.share_count,
            save_count=r.save_count,
            hashtags=r.hashtags or [],
            overall_sentiment=r.overall_sentiment,
            overall_sentiment_score=r.overall_sentiment_score,
            overall_confidence=r.overall_confidence,
            aspects_breakdown=r.aspects_breakdown,
            keywords=r.keywords,
            risk_level=r.risk_level,
            risk_factors=r.risk_factors,
            primary_intent=r.primary_intent,
            intent_confidence=r.intent_confidence,
            is_spam=r.is_spam,
            engagement_score=r.engagement_score,
            virality_score=r.virality_score,
            influence_score=r.influence_score,
            impact_score=r.impact_score,
            processing_time_ms=r.processing_time_ms,
            model_version=r.model_version,
            processing_status=r.processing_status,
            analyzed_at=r.analyzed_at,
        )

    # ------------------------------------------------------------------
    # Private helpers: per-phase processing
    # ------------------------------------------------------------------

    def _run_stages_1_to_3(self, uap: UAPRecord, project_id: str) -> tuple:
        """Stages 1-3 for a single record.

        Returns:
            (result, full_text, keywords_for_sentiment, skip_sentiment)
            where skip_sentiment=True means sentiment/impact should not run.
        """
        ingest = uap.ingest
        source_id = ingest.source.source_id if ingest.source else None
        source_type = ingest.source.source_type if ingest.source else PLATFORM_UNKNOWN
        platform = normalize_platform(source_type)

        content = uap.content
        text = content.text if content else ""
        published_at = _parse_datetime(content.published_at if content else None)

        author = content.author if content else None
        author_followers = author.followers if author and author.followers else 0
        author_is_verified = author.is_verified if author else False

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

        result.view_count = views
        result.like_count = likes
        result.comment_count = comments
        result.share_count = shares
        result.save_count = saves
        result.follower_count = author_followers

        add_uap_metadata(result, uap, self.config)

        full_text = text
        skip = False

        # === STAGE 1: PREPROCESSING ===
        if self.config.enable_preprocessing and self.preprocessor:
            try:
                tp_input = TPInput(
                    content=ContentInput(text=text, transcription=""),
                    comments=[],
                )
                tp_output = self.preprocessor.process(tp_input)
                result.is_spam = tp_output.is_spam
                result.spam_reasons = tp_output.spam_reasons
                full_text = tp_output.clean_text
                if result.is_spam:
                    result.risk_level = "LOW"
                    result.processing_status = "success_spam"
            except Exception as exc:
                self.logger.error(
                    f"internal.analytics.usecase.batch_enricher: preprocessing failed: {exc}"
                )

        # === STAGE 2: INTENT CLASSIFICATION ===
        if self.config.enable_intent_classification and self.intent_classifier:
            try:
                ic_input = IntentClassificationInput(text=full_text)
                ic_output = self.intent_classifier.process(ic_input)
                result.primary_intent = ic_output.intent.name
                result.intent_confidence = ic_output.confidence
                if ic_output.should_skip:
                    result.processing_status = "success_skipped"
                    result.risk_level = "LOW"
                    skip = True
                    return result, full_text, [], skip
            except Exception as exc:
                self.logger.error(
                    f"internal.analytics.usecase.batch_enricher: intent classification failed: {exc}"
                )

        # === STAGE 3: KEYWORD EXTRACTION ===
        keywords_for_sentiment = []
        if self.config.enable_keyword_extraction and self.keyword_extractor:
            try:
                ke_input = KeywordExtractionInput(text=full_text)
                ke_output = self.keyword_extractor.process(ke_input)
                result.keywords = [kw.keyword for kw in ke_output.keywords]
                keywords_for_sentiment = ke_output.keywords
            except Exception as exc:
                self.logger.error(
                    f"internal.analytics.usecase.batch_enricher: keyword extraction failed: {exc}"
                )

        return result, full_text, keywords_for_sentiment, skip

    def _apply_sentiment_result(self, result: AnalyticsResult, sa_output) -> None:
        """Apply a pre-computed sentiment Output to an AnalyticsResult."""
        try:
            result.overall_sentiment = sa_output.overall.label
            result.overall_sentiment_score = sa_output.overall.score
            result.overall_confidence = sa_output.overall.confidence
            if sa_output.overall.probabilities:
                result.sentiment_probabilities = sa_output.overall.probabilities
            aspects_list = []
            for aspect_name, aspect_sentiment in sa_output.aspects.items():
                aspects_list.append(
                    {
                        "aspect": aspect_name,
                        "polarity": aspect_sentiment.label,
                        "confidence": aspect_sentiment.confidence,
                        "score": aspect_sentiment.score,
                        "evidence": ", ".join(aspect_sentiment.keywords[:3])
                        if aspect_sentiment.keywords
                        else "",
                        "mentions": aspect_sentiment.mentions,
                        "rating": aspect_sentiment.rating,
                    }
                )
            if aspects_list:
                result.aspects_breakdown = {"aspects": aspects_list}
        except Exception as exc:
            self.logger.error(
                f"internal.analytics.usecase.batch_enricher: apply sentiment failed: {exc}"
            )

    def _run_impact_calculation(
        self, uap: UAPRecord, result: AnalyticsResult, full_text: str
    ) -> None:
        """Stage 5: impact calculation for a single record."""
        content = uap.content
        author = content.author if content else None
        author_followers = author.followers if author and author.followers else 0
        author_is_verified = author.is_verified if author else False

        signals = uap.signals
        engagement = signals.engagement if signals else None
        views = engagement.view_count if engagement else 0
        likes = engagement.like_count if engagement else 0
        comments = engagement.comment_count if engagement else 0
        shares = engagement.share_count if engagement else 0
        saves = engagement.save_count if engagement else 0

        try:
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
                    is_verified=author_is_verified,
                ),
                sentiment=SentimentInput(
                    label=result.overall_sentiment,
                    score=result.overall_sentiment_score,
                ),
                platform=result.platform,
                text=full_text,
            )
            ic_output = self.impact_calculator.process(ic_input)
            result.impact_score = ic_output.impact_score
            result.risk_level = ic_output.risk_level
            result.is_viral = ic_output.is_viral
            result.is_kol = ic_output.is_kol
            result.engagement_score = ic_output.engagement_score
            result.virality_score = ic_output.virality_score
            result.influence_score = ic_output.influence_score
            result.risk_factors = ic_output.risk_factors
            if ic_output.impact_breakdown:
                result.impact_breakdown = {
                    "engagement_score": ic_output.impact_breakdown.engagement_score,
                    "reach_score": ic_output.impact_breakdown.reach_score,
                    "platform_multiplier": ic_output.impact_breakdown.platform_multiplier,
                    "sentiment_amplifier": ic_output.impact_breakdown.sentiment_amplifier,
                    "raw_impact": ic_output.impact_breakdown.raw_impact,
                }
        except Exception as exc:
            self.logger.error(
                f"internal.analytics.usecase.batch_enricher: impact calculation failed: {exc}"
            )


__all__ = ["NLPBatchEnricher"]
