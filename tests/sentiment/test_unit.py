"""Unit tests for SentimentAnalyzer (Aspect-Based Sentiment Analyzer)."""

from typing import Any, Dict, List

import pytest  # type: ignore

from infrastructure.ai.constants import (
    ABSA_LABELS,
    DEFAULT_CONTEXT_WINDOW_SIZE,
    SCORE_MAP,
    THRESHOLD_NEGATIVE,
    THRESHOLD_POSITIVE,
)
from services.analytics.sentiment import SentimentAnalyzer


class FakePhoBERT:
    """Simple fake PhoBERT model for unit testing.

    This fake model ignores the input text and returns a configurable
    rating, confidence and probabilities so we can test ABSA logic
    without loading the real ONNX model.
    """

    def __init__(self, rating: int = 3, confidence: float = 0.8):
        self.rating = rating
        self.confidence = confidence

    def predict(self, text: str, return_probabilities: bool = True) -> Dict[str, Any]:
        # Minimal stub that mimics PhoBERTONNX.predict() contract
        result: Dict[str, Any] = {
            "rating": self.rating,
            "sentiment": "DUMMY",
            "confidence": self.confidence,
        }
        if return_probabilities:
            # Return dummy 5-class distribution
            result["probabilities"] = {
                "VERY_NEGATIVE": 0.2,
                "NEGATIVE": 0.2,
                "NEUTRAL": 0.2,
                "POSITIVE": 0.2,
                "VERY_POSITIVE": 0.2,
            }
        return result


@pytest.fixture
def analyzer() -> SentimentAnalyzer:
    """Return SentimentAnalyzer with fake PhoBERT."""

    fake_model = FakePhoBERT()
    return SentimentAnalyzer(fake_model)


class TestOverallSentiment:
    """Tests for overall sentiment analysis and conversion."""

    def test_empty_text_returns_neutral(self, analyzer: SentimentAnalyzer) -> None:
        """Empty or whitespace text returns neutral with 0 confidence."""
        result = analyzer.analyze("", [])

        assert result["overall"]["label"] == ABSA_LABELS["NEUTRAL"]
        assert result["overall"]["score"] == 0.0
        assert result["overall"]["confidence"] == 0.0
        assert result["aspects"] == {}

    @pytest.mark.parametrize(
        "rating,expected_score,expected_label",
        [
            (1, SCORE_MAP[1], ABSA_LABELS["NEGATIVE"]),
            (2, SCORE_MAP[2], ABSA_LABELS["NEGATIVE"]),
            (3, SCORE_MAP[3], ABSA_LABELS["NEUTRAL"]),
            (4, SCORE_MAP[4], ABSA_LABELS["POSITIVE"]),
            (5, SCORE_MAP[5], ABSA_LABELS["POSITIVE"]),
        ],
    )
    def test_convert_5_class_to_3_class(
        self,
        rating: int,
        expected_score: float,
        expected_label: str,
    ) -> None:
        """Test _convert_to_absa_format mapping for all 5 classes."""
        fake_model = FakePhoBERT(rating=rating, confidence=0.9)
        analyzer = SentimentAnalyzer(fake_model)

        phobert_result = fake_model.predict("dummy text", return_probabilities=True)
        absa = analyzer._convert_to_absa_format(phobert_result)

        assert absa["score"] == expected_score
        assert absa["label"] == expected_label
        assert absa["confidence"] == pytest.approx(0.9, rel=1e-6)
        assert "probabilities" in absa


class TestContextWindowExtraction:
    """Tests for _extract_smart_window logic."""

    @pytest.fixture
    def long_text(self) -> str:
        return "Xe chạy rất êm ái nhưng giá hơi cao so với phân khúc thị trường hiện tại."

    def test_keyword_within_text(self, analyzer: SentimentAnalyzer, long_text: str) -> None:
        """Keyword in the middle should produce a meaningful context window."""
        keyword = "giá"
        position = long_text.find(keyword)

        context = analyzer._extract_smart_window(long_text, keyword, position)

        assert keyword in context
        # Context should not be empty and shorter than or equal to original text
        assert 0 < len(context) <= len(long_text)

    def test_keyword_at_start(self, analyzer: SentimentAnalyzer) -> None:
        """Keyword at text start uses left boundary correctly."""
        text = "Giá đắt quá so với chất lượng"
        keyword = "Giá"

        context = analyzer._extract_smart_window(text, keyword, position=0)

        assert "Giá đắt quá" in context

    def test_keyword_not_found_returns_full_text(self, analyzer: SentimentAnalyzer) -> None:
        """If keyword is not found, full text is used as fallback."""
        text = "Xe đẹp lắm"
        keyword = "giá"

        context = analyzer._extract_smart_window(text, keyword, position=None)

        assert context == text

    def test_text_shorter_than_window(self, analyzer: SentimentAnalyzer) -> None:
        """If text is shorter than window, return full text."""
        text = "Rất đẹp"
        keyword = "đẹp"

        context = analyzer._extract_smart_window(text, keyword, position=2)

        assert context == text


class TestAggregation:
    """Tests for _aggregate_scores weighted aggregation logic."""

    @pytest.fixture
    def base_results(self) -> List[Dict[str, Any]]:
        return [
            {"label": ABSA_LABELS["NEGATIVE"], "score": -0.8, "confidence": 0.95, "keyword": "pin"},
            {"label": ABSA_LABELS["NEGATIVE"], "score": -0.6, "confidence": 0.70, "keyword": "sạc"},
        ]

    def test_single_result_no_aggregation(self, analyzer: SentimentAnalyzer) -> None:
        """Single result should be returned as-is with mentions=1."""
        result = analyzer._aggregate_scores(
            [
                {
                    "label": ABSA_LABELS["POSITIVE"],
                    "score": 0.8,
                    "confidence": 0.9,
                    "keyword": "thiết kế",
                }
            ]
        )

        assert result["label"] == ABSA_LABELS["POSITIVE"]
        assert result["score"] == pytest.approx(0.8, rel=1e-6)
        assert result["mentions"] == 1
        assert result["keywords"] == ["thiết kế"]

    def test_multiple_results_weighted_average(
        self,
        analyzer: SentimentAnalyzer,
        base_results: List[Dict[str, Any]],
    ) -> None:
        """Multiple results should be aggregated with confidence weighting."""
        aggregated = analyzer._aggregate_scores(base_results)

        # Weighted average from spec example
        total_weighted = -0.8 * 0.95 + -0.6 * 0.70
        total_conf = 0.95 + 0.70
        expected_score = total_weighted / total_conf

        # Implementation rounds score to 3 decimals, so compare rounded values
        assert aggregated["score"] == round(expected_score, 3)
        assert aggregated["label"] == ABSA_LABELS["NEGATIVE"]
        assert aggregated["mentions"] == 2
        assert set(aggregated["keywords"]) == {"pin", "sạc"}

    def test_conflicting_sentiments_result_in_neutral(self, analyzer: SentimentAnalyzer) -> None:
        """Conflicting positive & negative scores should average to neutral around 0."""
        results = [
            {
                "label": ABSA_LABELS["POSITIVE"],
                "score": 0.8,
                "confidence": 0.9,
                "keyword": "giá rẻ",
            },
            {
                "label": ABSA_LABELS["NEGATIVE"],
                "score": -0.7,
                "confidence": 0.85,
                "keyword": "giá cao",
            },
        ]

        aggregated = analyzer._aggregate_scores(results)

        assert aggregated["label"] == ABSA_LABELS["NEUTRAL"]
        assert abs(aggregated["score"]) < THRESHOLD_POSITIVE


class TestAnalyzeAPI:
    """High-level tests for analyze() behaviour."""

    def test_analyze_without_keywords_returns_overall_only(self) -> None:
        """If no keywords are provided, only overall sentiment is returned."""
        fake_model = FakePhoBERT(rating=4, confidence=0.9)
        analyzer = SentimentAnalyzer(fake_model)

        result = analyzer.analyze("Xe rất đẹp", keywords=None)

        assert result["overall"]["label"] == ABSA_LABELS["POSITIVE"]
        assert result["aspects"] == {}

    def test_analyze_with_keywords_groups_by_aspect(self) -> None:
        """Keywords with aspects are grouped and analyzed per aspect."""
        fake_model = FakePhoBERT(rating=5, confidence=0.95)
        analyzer = SentimentAnalyzer(fake_model, context_window_size=DEFAULT_CONTEXT_WINDOW_SIZE)

        text = "Xe thiết kế đẹp nhưng giá hơi cao"
        keywords = [
            {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")},
            {"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")},
        ]

        result = analyzer.analyze(text, keywords)

        assert "DESIGN" in result["aspects"]
        assert "PRICE" in result["aspects"]
        assert result["aspects"]["DESIGN"]["label"] == ABSA_LABELS["POSITIVE"]
        assert result["aspects"]["PRICE"]["label"] == ABSA_LABELS["POSITIVE"]
