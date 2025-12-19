"""Analytics Orchestrator - central pipeline coordinator.

This module implements `AnalyticsOrchestrator`, a thin orchestration layer that:

1. Accepts a single Atomic JSON post (`post_data: dict`).
2. Runs the 5 core modules in order:
   Preprocessor → Intent → Keyword → Sentiment → Impact.
3. Applies skip logic for spam/seeding/noise.
4. Builds a final analytics payload compatible with `PostAnalytics`.
5. Delegates persistence to an injected repository.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from core.logger import logger
from services.analytics.preprocessing.text_preprocessor import (
    TextPreprocessor,
    PreprocessingResult,
)
from services.analytics.intent.intent_classifier import IntentClassifier
from services.analytics.keyword.keyword_extractor import KeywordExtractor, KeywordResult
from services.analytics.sentiment import SentimentAnalyzer
from services.analytics.impact import ImpactCalculator


@runtime_checkable
class AnalyticsRepositoryProtocol(Protocol):
    """Protocol defining the repository interface for type safety."""

    def save(self, analytics_data: Dict[str, Any]) -> Any:
        """Save analytics data to persistent storage."""
        ...


class AnalyticsOrchestrator:
    """Coordinate the analytics pipeline for a single Atomic JSON post.

    The orchestrator is intentionally thin: it wires together existing modules
    and shapes data, but does not embed model-specific business logic.
    """

    # Model version for tracking which version processed the post
    MODEL_VERSION = "1.0.0"

    def __init__(
        self,
        repository: AnalyticsRepositoryProtocol,
        *,
        preprocessor: Optional[TextPreprocessor] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        keyword_extractor: Optional[KeywordExtractor] = None,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        impact_calculator: Optional[ImpactCalculator] = None,
    ) -> None:
        """Initialize orchestrator with module dependencies and repository.

        Args:
            repository: Persistence abstraction providing a `save(dict) -> Any` method.
            preprocessor: TextPreprocessor instance (optional).
            intent_classifier: IntentClassifier instance (optional).
            keyword_extractor: KeywordExtractor instance (optional).
            sentiment_analyzer: SentimentAnalyzer instance (optional).
            impact_calculator: ImpactCalculator instance (optional).

        Raises:
            TypeError: If repository does not implement required interface.
        """
        if not callable(getattr(repository, "save", None)):
            raise TypeError("repository must implement save(dict) method")

        self.repository = repository
        self.preprocessor = preprocessor or TextPreprocessor()
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.keyword_extractor = keyword_extractor or KeywordExtractor()
        self.sentiment_analyzer = sentiment_analyzer
        self.impact_calculator = impact_calculator or ImpactCalculator()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def process_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full analytics pipeline for a single Atomic JSON post.

        This method orchestrates:
        1. Preprocessing
        2. Intent classification & skip logic
        3. Keyword extraction
        4. Sentiment analysis
        5. Impact calculation
        6. Persistence via repository

        Args:
            post_data: Atomic JSON post with meta, content, interaction, author, comments.

        Returns:
            Analytics payload dict compatible with PostAnalytics model.

        Raises:
            ValueError: If post_data is missing required 'meta.id' field.
        """
        start_time = time.perf_counter()

        meta = post_data.get("meta") or {}
        post_id = meta.get("id")

        if not post_id:
            raise ValueError("post_data must contain 'meta.id' field")

        logger.info(f"Starting analytics pipeline for post_id={post_id}")

        # --- STEP 1: PREPROCESS ---
        prep_result = self._run_preprocessor(post_data)

        # --- STEP 2: INTENT (GATEKEEPER) ---
        intent_result = self.intent_classifier.predict(prep_result.clean_text)

        # Skip logic: use both preprocessor stats & intent gate
        if self._should_skip(prep_result, intent_result):
            processing_time_ms = int((time.perf_counter() - start_time) * 1000)
            analytics_payload = self._build_skipped_result(
                post_data, prep_result, intent_result, processing_time_ms=processing_time_ms
            )
            self.repository.save(analytics_payload)
            intent = intent_result.get("intent")
            logger.info(
                f"Skipped noisy/spam post_id={post_id} with intent={intent} in {processing_time_ms}ms"
            )
            return analytics_payload

        # --- STEP 3: KEYWORD EXTRACTION ---
        keyword_result = self._run_keywords(prep_result.clean_text)

        # --- STEP 4: SENTIMENT ANALYSIS ---
        sentiment_result = self._run_sentiment(prep_result.clean_text, keyword_result.keywords)

        # --- STEP 5: IMPACT CALCULATION ---
        impact_result = self._run_impact(post_data, sentiment_result)

        # --- STEP 6: BUILD & PERSIST RESULT ---
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)
        analytics_payload = self._build_final_result(
            post_data,
            prep_result,
            intent_result,
            keyword_result,
            sentiment_result,
            impact_result,
            processing_time_ms=processing_time_ms,
        )
        self.repository.save(analytics_payload)
        logger.info(f"Successfully processed post_id={post_id} in {processing_time_ms}ms")
        return analytics_payload

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _run_preprocessor(self, post_data: Dict[str, Any]) -> PreprocessingResult:
        content = post_data.get("content", {}) or {}
        comments = post_data.get("comments", []) or []

        preprocessor_input = {
            "content": {
                "text": content.get("text") or content.get("description") or "",
                "transcription": content.get("transcription") or "",
            },
            "comments": comments,
        }
        return self.preprocessor.preprocess(preprocessor_input)

    def _should_skip(self, prep: PreprocessingResult, intent_result: Any) -> bool:
        """Determine if post should be skipped based on preprocessing and intent.

        Args:
            prep: Preprocessing result with stats.
            intent_result: Intent classification result (dict or IntentResult dataclass).

        Returns:
            True if post should be skipped (spam/seeding/noise).
        """
        stats = prep.stats or {}
        is_too_short = bool(stats.get("is_too_short"))
        has_spam_keyword = bool(stats.get("has_spam_keyword"))

        # Handle both dict and IntentResult dataclass
        if hasattr(intent_result, "should_skip"):
            should_skip_intent = bool(intent_result.should_skip)
        else:
            should_skip_intent = bool(intent_result.get("should_skip"))

        return is_too_short or has_spam_keyword or should_skip_intent

    def _run_keywords(self, clean_text: str) -> KeywordResult:
        """Run keyword extraction with graceful fallback."""
        try:
            return self.keyword_extractor.extract(clean_text)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error(f"Keyword extraction failed: {exc}")
            # Fallback to empty keyword set so downstream sentiment/impact still work.
            return KeywordResult(keywords=[], metadata={"error": str(exc)})

    def _run_sentiment(self, clean_text: str, keywords: Any) -> Dict[str, Any]:
        if not self.sentiment_analyzer:
            # Sentiment layer may be disabled in some environments; degrade gracefully.
            logger.warning("SentimentAnalyzer is not configured; returning neutral defaults.")
            return {
                "overall": {
                    "label": "NEUTRAL",
                    "score": 0.0,
                    "confidence": 0.0,
                    "probabilities": {},
                },
                "aspects": {},
            }
        try:
            return self.sentiment_analyzer.analyze(clean_text, keywords)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error(f"Sentiment analysis failed: {exc}")
            # Fallback to neutral sentiment so ImpactCalculator can still run.
            return {
                "overall": {
                    "label": "NEUTRAL",
                    "score": 0.0,
                    "confidence": 0.0,
                    "probabilities": {},
                },
                "aspects": {},
            }

    def _run_impact(
        self, post_data: Dict[str, Any], sentiment_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        interaction = post_data.get("interaction", {}) or {}
        author = post_data.get("author", {}) or {}
        platform = (post_data.get("meta", {}) or {}).get("platform", "UNKNOWN")
        overall = sentiment_result.get("overall") or {}

        try:
            return self.impact_calculator.calculate(
                interaction=interaction,
                author=author,
                sentiment=overall,
                platform=str(platform).upper(),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error(f"Impact calculation failed: {exc}")
            # Fallback to neutral/low impact to keep record consistent.
            return {
                "impact_score": 0.0,
                "risk_level": "LOW",
                "is_viral": False,
                "is_kol": False,
                "impact_breakdown": {
                    "engagement_score": 0.0,
                    "reach_score": 0.0,
                    "platform_multiplier": 1.0,
                    "sentiment_amplifier": 1.0,
                    "raw_impact": 0.0,
                },
            }

    def _build_skipped_result(
        self,
        post_data: Dict[str, Any],
        prep: PreprocessingResult,
        intent_result: Any,
        *,
        processing_time_ms: int = 0,
    ) -> Dict[str, Any]:
        """Build a minimal analytics record for skipped posts."""
        meta = post_data.get("meta", {}) or {}
        interaction = post_data.get("interaction", {}) or {}
        author = post_data.get("author", {}) or {}

        now = datetime.now(timezone.utc)
        published_at = meta.get("published_at")
        if published_at is None:
            published_at = now

        # Extract intent info from dict or dataclass
        intent_name, intent_confidence = self._extract_intent_info(intent_result)

        # Extract crawler metadata from enriched meta
        crawler_metadata = self._extract_crawler_metadata(meta)

        result = {
            # Identifiers & metadata
            "id": meta.get("id"),
            "project_id": meta.get("project_id"),
            "platform": self._normalize_platform(meta.get("platform")),
            "published_at": published_at,
            "analyzed_at": now,
            # Overall analysis defaults
            "overall_sentiment": "NEUTRAL",
            "overall_sentiment_score": 0.0,
            "overall_confidence": 0.0,
            # Intent
            "primary_intent": intent_name,
            "intent_confidence": intent_confidence,
            # Impact (neutral/low by design)
            "impact_score": 0.0,
            "risk_level": "LOW",
            "is_viral": False,
            "is_kol": False,
            # JSONB breakdowns
            "aspects_breakdown": {},
            "keywords": [],
            "sentiment_probabilities": {},
            "impact_breakdown": {},
            # Raw metrics
            "view_count": self._safe_int(interaction.get("views")),
            "like_count": self._safe_int(interaction.get("likes")),
            "comment_count": self._safe_int(interaction.get("comments_count")),
            "share_count": self._safe_int(interaction.get("shares")),
            "save_count": self._safe_int(interaction.get("saves")),
            "follower_count": self._safe_int(author.get("followers")),
            # Processing metadata
            "processing_time_ms": processing_time_ms,
            "model_version": self.MODEL_VERSION,
        }

        # Add crawler metadata
        result.update(crawler_metadata)

        return result

    def _extract_intent_info(self, intent_result: Any) -> tuple[str, float]:
        """Extract intent name and confidence from dict or IntentResult.

        Args:
            intent_result: Intent classification result (dict or IntentResult dataclass).

        Returns:
            Tuple of (intent_name, confidence).
        """
        if hasattr(intent_result, "intent"):
            # IntentResult dataclass
            intent = intent_result.intent
            # Handle Intent enum
            intent_name = str(intent.name) if hasattr(intent, "name") else str(intent)
            confidence = float(getattr(intent_result, "confidence", 0.0))
        else:
            # Dict
            intent_name = str(intent_result.get("intent", "DISCUSSION"))
            confidence = float(intent_result.get("confidence", 0.0))
        return intent_name, confidence

    @staticmethod
    def _normalize_platform(platform: Optional[str]) -> str:
        """Normalize platform name to uppercase."""
        if not platform:
            return "UNKNOWN"
        return str(platform).strip().upper()

    @staticmethod
    def _extract_crawler_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract crawler metadata fields from enriched meta.

        These fields are added by enrich_with_batch_context() in the consumer
        and need to be passed through to the final analytics payload.

        Args:
            meta: Post metadata dictionary (may contain crawler fields)

        Returns:
            Dictionary with crawler metadata fields (only non-None values)
        """
        crawler_fields = [
            # Batch context
            "job_id",
            "batch_index",
            "task_type",
            "keyword_source",
            "crawled_at",
            "pipeline_version",
            # NEW: Brand/Keyword (Contract v2.0)
            "brand_name",
            "keyword",
            # NEW: Content fields (Contract v2.0)
            "content_text",
            "content_transcription",
            "media_duration",
            "hashtags",
            "permalink",
            # NEW: Author fields (Contract v2.0)
            "author_id",
            "author_name",
            "author_username",
            "author_avatar_url",
            "author_is_verified",
        ]

        result = {}
        missing_fields = []

        for field in crawler_fields:
            value = meta.get(field)
            if value is not None:
                result[field] = value
            else:
                missing_fields.append(field)

        # Log debug info about extracted metadata
        if result:
            logger.debug(
                "Extracted crawler metadata: %s",
                {k: v for k, v in result.items() if k != "crawled_at"},
            )

        if missing_fields:
            logger.debug(
                "Missing crawler metadata fields (will be NULL): %s",
                missing_fields,
            )

        return result

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Safely convert value to int with default fallback."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _build_final_result(
        self,
        post_data: Dict[str, Any],
        prep: PreprocessingResult,
        intent_result: Any,
        keyword_result: Any,
        sentiment_result: Dict[str, Any],
        impact_result: Dict[str, Any],
        *,
        processing_time_ms: int = 0,
    ) -> Dict[str, Any]:
        """Build final analytics payload from all module outputs."""
        meta = post_data.get("meta", {}) or {}
        interaction = post_data.get("interaction", {}) or {}
        author = post_data.get("author", {}) or {}

        overall = sentiment_result.get("overall") or {}

        now = datetime.now(timezone.utc)
        published_at = meta.get("published_at")
        if published_at is None:
            published_at = now

        # Extract intent info from dict or dataclass
        intent_name, intent_confidence = self._extract_intent_info(intent_result)

        # Extract crawler metadata from enriched meta
        crawler_metadata = self._extract_crawler_metadata(meta)

        result = {
            # Identifiers & metadata
            "id": meta.get("id"),
            "project_id": meta.get("project_id"),
            "platform": self._normalize_platform(meta.get("platform")),
            "published_at": published_at,
            "analyzed_at": now,
            # Overall analysis
            "overall_sentiment": overall.get("label", "NEUTRAL"),
            "overall_sentiment_score": float(overall.get("score", 0.0) or 0.0),
            "overall_confidence": float(overall.get("confidence", 0.0) or 0.0),
            # Intent
            "primary_intent": intent_name,
            "intent_confidence": intent_confidence,
            # Impact
            "impact_score": float(impact_result.get("impact_score", 0.0) or 0.0),
            "risk_level": impact_result.get("risk_level", "LOW"),
            "is_viral": bool(impact_result.get("is_viral", False)),
            "is_kol": bool(impact_result.get("is_kol", False)),
            # JSONB breakdowns
            "aspects_breakdown": sentiment_result.get("aspects") or {},
            "keywords": keyword_result.keywords if keyword_result else [],
            "sentiment_probabilities": overall.get("probabilities") or {},
            "impact_breakdown": impact_result.get("impact_breakdown") or {},
            # Raw metrics
            "view_count": self._safe_int(interaction.get("views")),
            "like_count": self._safe_int(interaction.get("likes")),
            "comment_count": self._safe_int(interaction.get("comments_count")),
            "share_count": self._safe_int(interaction.get("shares")),
            "save_count": self._safe_int(interaction.get("saves")),
            "follower_count": self._safe_int(author.get("followers")),
            # Processing metadata
            "processing_time_ms": processing_time_ms,
            "model_version": self.MODEL_VERSION,
        }

        # Add crawler metadata
        result.update(crawler_metadata)

        return result
