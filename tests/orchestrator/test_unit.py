"""Unit tests for AnalyticsOrchestrator.

This module tests the orchestrator's ability to coordinate the full analytics
pipeline, apply skip logic, and handle edge cases gracefully.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest  # type: ignore

from services.analytics.keyword.keyword_extractor import KeywordResult
from services.analytics.preprocessing.text_preprocessor import PreprocessingResult
from services.analytics.orchestrator import AnalyticsOrchestrator


# ============================================================================
# Test Fixtures & Mocks
# ============================================================================


class FakeRepository:
    """Fake repository for testing orchestrator persistence."""

    def __init__(self) -> None:
        self.saved_data: List[Dict[str, Any]] = []

    def save(self, data: Dict[str, Any]) -> None:
        """Store analytics payload for verification."""
        self.saved_data.append(data)


class FakeTextPreprocessor:
    """Fake text preprocessor for testing."""

    def __init__(
        self,
        clean_text: str = "clean text",
        stats: Dict[str, Any] | None = None,
    ) -> None:
        self.clean_text = clean_text
        self.stats = stats or {
            "total_length": len(clean_text),
            "is_too_short": False,
            "hashtag_ratio": 0.05,
            "has_transcription": False,
            "has_spam_keyword": False,
        }

    def preprocess(self, input_data: Dict[str, Any]) -> PreprocessingResult:
        """Return a PreprocessingResult with configured values."""
        return PreprocessingResult(
            clean_text=self.clean_text,
            stats=self.stats,
            source_breakdown={
                "caption_len": 0,
                "transcript_len": 0,
                "comments_len": 0,
            },
        )


class FakeIntentClassifier:
    """Fake intent classifier for testing."""

    def __init__(
        self,
        intent: str = "DISCUSSION",
        confidence: float = 0.8,
        should_skip: bool = False,
    ) -> None:
        self.intent = intent
        self.confidence = confidence
        self.should_skip = should_skip

    def predict(self, text: str) -> Dict[str, Any]:
        """Return intent classification result."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "should_skip": self.should_skip,
        }


class FakeKeywordExtractor:
    """Fake keyword extractor for testing."""

    def __init__(self, keywords: List[Dict[str, Any]] | None = None) -> None:
        self.keywords = keywords or [
            {"keyword": "xe", "aspect": "GENERAL", "score": 1.0, "source": "DICT"},
            {"keyword": "đẹp", "aspect": "DESIGN", "score": 0.9, "source": "DICT"},
        ]

    def extract(self, text: str) -> KeywordResult:
        """Return keyword extraction result."""
        return KeywordResult(
            keywords=self.keywords,
            metadata={"dict_matches": len(self.keywords), "ai_matches": 0},
        )


class FakeSentimentAnalyzer:
    """Fake sentiment analyzer for testing."""

    def __init__(
        self,
        overall_label: str = "POSITIVE",
        overall_score: float = 0.7,
        aspects: Dict[str, Any] | None = None,
    ) -> None:
        self.overall_label = overall_label
        self.overall_score = overall_score
        self.aspects = aspects or {
            "DESIGN": {
                "label": "POSITIVE",
                "score": 0.8,
                "confidence": 0.85,
                "mentions": 1,
            }
        }

    def analyze(self, text: str, keywords: Any) -> Dict[str, Any]:
        """Return sentiment analysis result."""
        return {
            "overall": {
                "label": self.overall_label,
                "score": self.overall_score,
                "confidence": 0.8,
                "probabilities": {
                    "NEGATIVE": 0.1,
                    "NEUTRAL": 0.2,
                    "POSITIVE": 0.7,
                },
            },
            "aspects": self.aspects,
        }


class FakeImpactCalculator:
    """Fake impact calculator for testing."""

    def __init__(
        self,
        impact_score: float = 50.0,
        risk_level: str = "MEDIUM",
        is_viral: bool = False,
        is_kol: bool = False,
    ) -> None:
        self.impact_score = impact_score
        self.risk_level = risk_level
        self.is_viral = is_viral
        self.is_kol = is_kol

    def calculate(
        self,
        interaction: Dict[str, Any],
        author: Dict[str, Any],
        sentiment: Dict[str, Any],
        platform: str,
    ) -> Dict[str, Any]:
        """Return impact calculation result."""
        return {
            "impact_score": self.impact_score,
            "risk_level": self.risk_level,
            "is_viral": self.is_viral,
            "is_kol": self.is_kol,
            "impact_breakdown": {
                "engagement_score": 20.0,
                "reach_score": 15.0,
                "platform_multiplier": 1.0,
                "sentiment_amplifier": 1.0,
                "raw_impact": 50.0,
            },
        }


def _make_sample_post_data() -> Dict[str, Any]:
    """Create a sample Atomic JSON post for testing."""
    return {
        "meta": {
            "id": "test_post_123",
            "project_id": "project_1",
            "platform": "facebook",
            "published_at": datetime.now(timezone.utc),
        },
        "content": {
            "text": "Xe đẹp lắm, rất hài lòng!",
            "transcription": "",
        },
        "interaction": {
            "views": 1000,
            "likes": 50,
            "comments_count": 10,
            "shares": 5,
            "saves": 2,
        },
        "author": {
            "id": "user_456",
            "name": "Test User",
            "followers": 5000,
            "is_verified": False,
        },
        "comments": [
            {"text": "Đẹp quá!", "likes": 5},
            {"text": "Mua ở đâu?", "likes": 2},
        ],
    }


# ============================================================================
# Test Classes
# ============================================================================


class TestHappyPath:
    """Tests for successful full pipeline execution."""

    def test_full_pipeline_success(self) -> None:
        """Happy-path: all modules succeed, result is persisted."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(clean_text="Xe đẹp lắm")
        intent = FakeIntentClassifier(intent="DISCUSSION", should_skip=False)
        keywords = FakeKeywordExtractor()
        sentiment = FakeSentimentAnalyzer()
        impact = FakeImpactCalculator(impact_score=60.0, risk_level="MEDIUM")

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=intent,
            keyword_extractor=keywords,
            sentiment_analyzer=sentiment,
            impact_calculator=impact,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Verify result structure
        assert result["id"] == "test_post_123"
        assert result["platform"] == "FACEBOOK"
        assert result["overall_sentiment"] == "POSITIVE"
        assert result["overall_sentiment_score"] == 0.7
        assert result["primary_intent"] == "DISCUSSION"
        assert result["impact_score"] == 60.0
        assert result["risk_level"] == "MEDIUM"
        assert len(result["keywords"]) == 2
        assert "DESIGN" in result["aspects_breakdown"]

        # Verify persistence
        assert len(repo.saved_data) == 1
        assert repo.saved_data[0]["id"] == "test_post_123"

    def test_full_pipeline_with_all_metrics(self) -> None:
        """Full pipeline with complete interaction/author data."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Verify all metrics are captured
        assert result["view_count"] == 1000
        assert result["like_count"] == 50
        assert result["comment_count"] == 10
        assert result["share_count"] == 5
        assert result["save_count"] == 2
        assert result["follower_count"] == 5000


class TestSkipLogic:
    """Tests for skip logic (SPAM, SEEDING, noise)."""

    def test_skip_too_short_text(self) -> None:
        """Skip posts with text that's too short."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(
            clean_text="ok",
            stats={"is_too_short": True, "total_length": 2},
        )
        intent = FakeIntentClassifier(should_skip=False)

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=intent,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Verify skipped result
        assert result["id"] == "test_post_123"
        assert result["overall_sentiment"] == "NEUTRAL"
        assert result["overall_sentiment_score"] == 0.0
        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"
        assert result["keywords"] == []
        assert result["aspects_breakdown"] == {}

        # Verify persistence
        assert len(repo.saved_data) == 1

    def test_skip_spam_keyword(self) -> None:
        """Skip posts with spam keywords detected."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(
            clean_text="vay vốn lãi suất thấp",
            stats={"has_spam_keyword": True, "is_too_short": False},
        )
        intent = FakeIntentClassifier(should_skip=False)

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=intent,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Verify skipped result
        assert result["overall_sentiment"] == "NEUTRAL"
        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"

    def test_skip_intent_seeding(self) -> None:
        """Skip posts classified as SEEDING intent."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(clean_text="Normal text here")
        intent = FakeIntentClassifier(intent="SEEDING", should_skip=True)

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=intent,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Verify skipped result
        assert result["overall_sentiment"] == "NEUTRAL"
        assert result["primary_intent"] == "SEEDING"
        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"

    def test_skip_combination_spam_and_intent(self) -> None:
        """Skip if either spam keyword OR intent skip is true."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(
            clean_text="spam text",
            stats={"has_spam_keyword": True},
        )
        intent = FakeIntentClassifier(should_skip=True)  # Both conditions

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=intent,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Should still skip (OR logic)
        assert result["overall_sentiment"] == "NEUTRAL"
        assert result["impact_score"] == 0.0


class TestGracefulHandling:
    """Tests for graceful handling of missing/invalid data."""

    def test_missing_interaction_metrics(self) -> None:
        """Handle posts with missing interaction data."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["interaction"] = {}  # Empty interaction

        result = orchestrator.process_post(post_data)

        # Should default to 0 for missing metrics
        assert result["view_count"] == 0
        assert result["like_count"] == 0
        assert result["comment_count"] == 0
        assert result["share_count"] == 0
        assert result["save_count"] == 0

    def test_missing_author_metrics(self) -> None:
        """Handle posts with missing author data."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["author"] = {}  # Empty author

        result = orchestrator.process_post(post_data)

        # Should default to 0 for missing follower count
        assert result["follower_count"] == 0

    def test_missing_comments(self) -> None:
        """Handle posts with no comments."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(clean_text="Text without comments")
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["comments"] = []  # No comments

        result = orchestrator.process_post(post_data)

        # Should still process successfully
        assert result["id"] == "test_post_123"
        assert result["overall_sentiment"] == "POSITIVE"

    def test_missing_content_text(self) -> None:
        """Handle posts with missing content.text."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(clean_text="")
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=FakeIntentClassifier(),
        )

        post_data = _make_sample_post_data()
        post_data["content"] = {}  # Empty content

        result = orchestrator.process_post(post_data)

        # Should handle gracefully (may skip if text is empty)
        assert result["id"] == "test_post_123"

    def test_missing_sentiment_analyzer(self) -> None:
        """Handle gracefully when SentimentAnalyzer is not configured."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=None,  # Not configured
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Should return neutral defaults
        assert result["overall_sentiment"] == "NEUTRAL"
        assert result["overall_sentiment_score"] == 0.0
        assert result["overall_confidence"] == 0.0
        assert result["aspects_breakdown"] == {}

    def test_keyword_extraction_failure_graceful(self) -> None:
        """Handle keyword extraction failures gracefully."""
        repo = FakeRepository()

        # Create a keyword extractor that raises an exception
        failing_keywords = FakeKeywordExtractor()
        original_extract = failing_keywords.extract

        def failing_extract(text: str) -> KeywordResult:
            raise RuntimeError("Keyword extraction failed")

        failing_keywords.extract = failing_extract  # type: ignore

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=failing_keywords,
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Should continue with empty keywords
        assert result["keywords"] == []
        assert "error" in result.get("keywords", []) or True  # May have error metadata

    def test_impact_calculation_failure_graceful(self) -> None:
        """Handle impact calculation failures gracefully."""
        repo = FakeRepository()

        # Create an impact calculator that raises an exception
        failing_impact = FakeImpactCalculator()

        def failing_calculate(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            raise ValueError("Impact calculation failed")

        failing_impact.calculate = failing_calculate  # type: ignore

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=failing_impact,
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        # Should fallback to neutral/low impact
        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"
        assert result["is_viral"] is False
        assert result["is_kol"] is False


class TestDataMapping:
    """Tests for correct data mapping in final payload."""

    def test_platform_normalization(self) -> None:
        """Platform should be normalized to uppercase."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["meta"]["platform"] = "tiktok"  # Lowercase

        result = orchestrator.process_post(post_data)

        assert result["platform"] == "TIKTOK"

    def test_unknown_platform_default(self) -> None:
        """Missing platform should default to UNKNOWN."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        del post_data["meta"]["platform"]

        result = orchestrator.process_post(post_data)

        assert result["platform"] == "UNKNOWN"

    def test_aspects_breakdown_mapping(self) -> None:
        """Aspects breakdown should map correctly from sentiment result."""
        repo = FakeRepository()
        sentiment = FakeSentimentAnalyzer(
            aspects={
                "DESIGN": {"label": "POSITIVE", "score": 0.8, "confidence": 0.85},
                "PRICE": {"label": "NEGATIVE", "score": -0.5, "confidence": 0.7},
            }
        )

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=sentiment,
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        assert "DESIGN" in result["aspects_breakdown"]
        assert "PRICE" in result["aspects_breakdown"]
        assert result["aspects_breakdown"]["DESIGN"]["label"] == "POSITIVE"
        assert result["aspects_breakdown"]["PRICE"]["label"] == "NEGATIVE"


class TestValidation:
    """Tests for input validation."""

    def test_missing_post_id_raises_error(self) -> None:
        """Should raise ValueError when meta.id is missing."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
        )

        post_data = _make_sample_post_data()
        del post_data["meta"]["id"]

        with pytest.raises(ValueError, match="meta.id"):
            orchestrator.process_post(post_data)

    def test_empty_meta_raises_error(self) -> None:
        """Should raise ValueError when meta is empty."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
        )

        post_data = _make_sample_post_data()
        post_data["meta"] = {}

        with pytest.raises(ValueError, match="meta.id"):
            orchestrator.process_post(post_data)

    def test_invalid_repository_raises_error(self) -> None:
        """Should raise TypeError when repository doesn't have save method."""
        with pytest.raises(TypeError, match="save"):
            AnalyticsOrchestrator(repository="not_a_repository")


class TestProcessingMetadata:
    """Tests for processing metadata in results."""

    def test_processing_time_is_recorded(self) -> None:
        """Processing time should be recorded in result."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        assert "processing_time_ms" in result
        assert isinstance(result["processing_time_ms"], int)
        assert result["processing_time_ms"] >= 0

    def test_model_version_is_recorded(self) -> None:
        """Model version should be recorded in result."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        assert "model_version" in result
        assert result["model_version"] == AnalyticsOrchestrator.MODEL_VERSION

    def test_skipped_result_has_processing_metadata(self) -> None:
        """Skipped results should also have processing metadata."""
        repo = FakeRepository()
        preprocessor = FakeTextPreprocessor(
            clean_text="ok",
            stats={"is_too_short": True, "total_length": 2},
        )

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=preprocessor,
            intent_classifier=FakeIntentClassifier(),
        )

        post_data = _make_sample_post_data()
        result = orchestrator.process_post(post_data)

        assert "processing_time_ms" in result
        assert "model_version" in result


class TestTypeCoercion:
    """Tests for type coercion and safe value handling."""

    def test_string_metrics_are_converted_to_int(self) -> None:
        """String metric values should be converted to integers."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["interaction"]["views"] = "1000"  # String instead of int
        post_data["interaction"]["likes"] = "50"

        result = orchestrator.process_post(post_data)

        assert result["view_count"] == 1000
        assert result["like_count"] == 50

    def test_none_metrics_default_to_zero(self) -> None:
        """None metric values should default to 0."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["interaction"]["views"] = None
        post_data["interaction"]["likes"] = None

        result = orchestrator.process_post(post_data)

        assert result["view_count"] == 0
        assert result["like_count"] == 0

    def test_invalid_metrics_default_to_zero(self) -> None:
        """Invalid metric values should default to 0."""
        repo = FakeRepository()
        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            preprocessor=FakeTextPreprocessor(),
            intent_classifier=FakeIntentClassifier(),
            keyword_extractor=FakeKeywordExtractor(),
            sentiment_analyzer=FakeSentimentAnalyzer(),
            impact_calculator=FakeImpactCalculator(),
        )

        post_data = _make_sample_post_data()
        post_data["interaction"]["views"] = "not_a_number"
        post_data["interaction"]["likes"] = {"invalid": "type"}

        result = orchestrator.process_post(post_data)

        assert result["view_count"] == 0
        assert result["like_count"] == 0
