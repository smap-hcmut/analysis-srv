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

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from services.analytics.preprocessing.text_preprocessor import (
    TextPreprocessor,
    PreprocessingResult,
)
from services.analytics.intent.intent_classifier import IntentClassifier
from services.analytics.keyword.keyword_extractor import KeywordExtractor, KeywordResult
from services.analytics.sentiment import SentimentAnalyzer
from services.analytics.impact import ImpactCalculator


logger = logging.getLogger(__name__)


class AnalyticsOrchestrator:
    """Coordinate the analytics pipeline for a single Atomic JSON post.

    The orchestrator is intentionally thin: it wires together existing modules
    and shapes data, but does not embed model-specific business logic.
    """

    def __init__(
        self,
        repository: Any,
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
        """
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
        """
        post_id = post_data.get("meta", {}).get("id")
        logger.info("Starting analytics pipeline for post_id=%s", post_id)

        # --- STEP 1: PREPROCESS ---
        prep_result = self._run_preprocessor(post_data)

        # --- STEP 2: INTENT (GATEKEEPER) ---
        intent_result = self.intent_classifier.predict(prep_result.clean_text)

        # Skip logic: use both preprocessor stats & intent gate
        if self._should_skip(prep_result, intent_result):
            analytics_payload = self._build_skipped_result(post_data, prep_result, intent_result)
            self.repository.save(analytics_payload)
            logger.info("Skipped noisy/spam post_id=%s with intent=%s", post_id, intent_result)
            return analytics_payload

        # --- STEP 3: KEYWORD EXTRACTION ---
        keyword_result = self._run_keywords(prep_result.clean_text)

        # --- STEP 4: SENTIMENT ANALYSIS ---
        sentiment_result = self._run_sentiment(prep_result.clean_text, keyword_result.keywords)

        # --- STEP 5: IMPACT CALCULATION ---
        impact_result = self._run_impact(post_data, sentiment_result)

        # --- STEP 6: BUILD & PERSIST RESULT ---
        analytics_payload = self._build_final_result(
            post_data,
            prep_result,
            intent_result,
            keyword_result,
            sentiment_result,
            impact_result,
        )
        self.repository.save(analytics_payload)
        logger.info("Successfully processed post_id=%s", post_id)
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

    def _should_skip(self, prep: PreprocessingResult, intent_result: Dict[str, Any]) -> bool:
        stats = prep.stats or {}
        is_too_short = bool(stats.get("is_too_short"))
        has_spam_keyword = bool(stats.get("has_spam_keyword"))
        should_skip_intent = bool(intent_result.get("should_skip"))
        return is_too_short or has_spam_keyword or should_skip_intent

    def _run_keywords(self, clean_text: str) -> KeywordResult:
        """Run keyword extraction with graceful fallback."""
        try:
            return self.keyword_extractor.extract(clean_text)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Keyword extraction failed: %s", exc)
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
            logger.error("Sentiment analysis failed: %s", exc)
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
            logger.error("Impact calculation failed: %s", exc)
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
        intent_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a minimal analytics record for skipped posts."""
        meta = post_data.get("meta", {}) or {}
        interaction = post_data.get("interaction", {}) or {}
        author = post_data.get("author", {}) or {}

        now = datetime.utcnow()
        return {
            # Identifiers & metadata
            "id": meta.get("id"),
            "project_id": meta.get("project_id"),
            "platform": (meta.get("platform") or "UNKNOWN").upper(),
            "published_at": meta.get("published_at") or now,
            "analyzed_at": now,
            # Overall analysis defaults
            "overall_sentiment": "NEUTRAL",
            "overall_sentiment_score": 0.0,
            "overall_confidence": 0.0,
            # Intent
            "primary_intent": intent_result.get("intent", "DISCUSSION"),
            "intent_confidence": intent_result.get("confidence", 0.0),
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
            "view_count": interaction.get("views", 0),
            "like_count": interaction.get("likes", 0),
            "comment_count": interaction.get("comments_count", 0),
            "share_count": interaction.get("shares", 0),
            "save_count": interaction.get("saves", 0),
            "follower_count": author.get("followers", 0),
        }

    def _build_final_result(
        self,
        post_data: Dict[str, Any],
        prep: PreprocessingResult,
        intent_result: Dict[str, Any],
        keyword_result: Any,
        sentiment_result: Dict[str, Any],
        impact_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build final analytics payload from all module outputs."""
        meta = post_data.get("meta", {}) or {}
        interaction = post_data.get("interaction", {}) or {}
        author = post_data.get("author", {}) or {}

        overall = sentiment_result.get("overall") or {}

        now = datetime.utcnow()
        return {
            # Identifiers & metadata
            "id": meta.get("id"),
            "project_id": meta.get("project_id"),
            "platform": (meta.get("platform") or "UNKNOWN").upper(),
            "published_at": meta.get("published_at") or now,
            "analyzed_at": now,
            # Overall analysis
            "overall_sentiment": overall.get("label"),
            "overall_sentiment_score": overall.get("score"),
            "overall_confidence": overall.get("confidence"),
            # Intent
            "primary_intent": intent_result.get("intent"),
            "intent_confidence": intent_result.get("confidence"),
            # Impact
            "impact_score": impact_result.get("impact_score"),
            "risk_level": impact_result.get("risk_level"),
            "is_viral": impact_result.get("is_viral"),
            "is_kol": impact_result.get("is_kol"),
            # JSONB breakdowns
            "aspects_breakdown": sentiment_result.get("aspects", {}),
            "keywords": keyword_result.keywords,
            "sentiment_probabilities": overall.get("probabilities", {}),
            "impact_breakdown": impact_result.get("impact_breakdown", {}),
            # Raw metrics
            "view_count": interaction.get("views", 0),
            "like_count": interaction.get("likes", 0),
            "comment_count": interaction.get("comments_count", 0),
            "share_count": interaction.get("shares", 0),
            "save_count": interaction.get("saves", 0),
            "follower_count": author.get("followers", 0),
        }
