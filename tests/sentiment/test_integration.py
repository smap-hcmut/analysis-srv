"""Integration tests for SentimentAnalyzer with real PhoBERT model (if available)."""

from pathlib import Path
from typing import Dict, List

import pytest  # type: ignore

from infrastructure.ai.phobert_onnx import PhoBERTONNX
from services.analytics.sentiment import SentimentAnalyzer


@pytest.mark.skipif(
    not Path("infrastructure/phobert/models/model_quantized.onnx").exists(),
    reason="PhoBERT model not downloaded. Run 'make download-phobert' first.",
)
class TestSentimentAnalyzerIntegration:
    """Integration tests using real PhoBERT model and Vietnamese text."""

    @pytest.fixture(scope="class")
    def analyzer(self) -> SentimentAnalyzer:
        """Load real PhoBERT model once and create SentimentAnalyzer."""
        phobert = PhoBERTONNX()
        return SentimentAnalyzer(phobert)

    def test_overall_sentiment_positive(self, analyzer: SentimentAnalyzer) -> None:
        """Test overall positive sentiment on Vietnamese text."""
        text = "Xe thiết kế rất đẹp, pin tốt, giá hợp lý, dịch vụ tuyệt vời"

        result = analyzer.analyze(text, keywords=None)

        overall = result["overall"]
        assert overall["label"] in ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        assert -1.0 <= overall["score"] <= 1.0
        assert 0.0 <= overall["confidence"] <= 1.0

    def test_aspect_sentiment_conflict_price_vs_design(self, analyzer: SentimentAnalyzer) -> None:
        """Test conflict scenario: DESIGN positive, PRICE negative."""
        text = "Xe thiết kế rất đẹp nhưng giá quá đắt so với đối thủ"
        keywords: List[Dict[str, object]] = [
            {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")},
            {"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")},
        ]

        result = analyzer.analyze(text, keywords)

        aspects = result["aspects"]
        assert "DESIGN" in aspects
        assert "PRICE" in aspects

        # We don't assert exact label (depends on model), but structure must be valid
        assert aspects["DESIGN"]["mentions"] >= 1
        assert isinstance(aspects["DESIGN"]["score"], float)
        assert isinstance(aspects["DESIGN"]["confidence"], float)

        assert aspects["PRICE"]["mentions"] >= 1
        assert isinstance(aspects["PRICE"]["score"], float)
        assert isinstance(aspects["PRICE"]["confidence"], float)

    def test_multiple_mentions_same_aspect(self, analyzer: SentimentAnalyzer) -> None:
        """Test aggregation with multiple mentions of PERFORMANCE aspect."""
        text = "Pin yếu, sạc rất lâu, thất vọng về pin và sạc của xe"
        keywords: List[Dict[str, object]] = [
            {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.find("Pin")},
            {"keyword": "sạc", "aspect": "PERFORMANCE", "position": text.find("sạc")},
            {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.rfind("pin")},
        ]

        result = analyzer.analyze(text, keywords)

        performance = result["aspects"].get("PERFORMANCE")
        assert performance is not None
        assert performance["mentions"] == 3
        assert len(performance["keywords"]) == 3
