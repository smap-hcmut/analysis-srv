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
        # Should be clearly positive overall
        assert overall["label"] == "POSITIVE"
        assert overall["score"] > 0
        assert 0.0 <= overall["confidence"] <= 1.0

    def test_overall_sentiment_negative_texts(self, analyzer: SentimentAnalyzer) -> None:
        """Negative Vietnamese texts must be classified as negative overall."""
        negative_texts = [
            "Sản phẩm dở tệ, chất lượng rất kém, không đáng mua",
            "Rất tệ, hoàn toàn thất vọng, không nên mua chiếc xe này",
            "Chất lượng kém, hay hỏng vặt, trải nghiệm rất tệ",
        ]

        for text in negative_texts:
            result = analyzer.analyze(text, keywords=None)
            overall = result["overall"]
            assert overall["label"] == "NEGATIVE", f"Expected NEGATIVE for: {text}"
            assert overall["score"] < 0, f"Expected negative score for: {text}"
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

        design = aspects["DESIGN"]
        price = aspects["PRICE"]

        # Semantic expectations:
        # - DESIGN aspect should not be negative (POSITIVE or NEUTRAL are both acceptable),
        #   since the text clearly praises the design even if price is a concern.
        assert design["label"] in ["POSITIVE", "NEUTRAL"]
        assert design["score"] >= 0
        assert design["mentions"] >= 1
        assert isinstance(design["confidence"], float)

        # - PRICE aspect should be negative
        assert price["label"] == "NEGATIVE"
        assert price["score"] < 0
        assert price["mentions"] >= 1
        assert isinstance(price["confidence"], float)

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

    def test_semantic_correctness_positive_aspects(self, analyzer: SentimentAnalyzer) -> None:
        """Positive-only examples for design and service should be POSITIVE."""
        # DESIGN praise
        text_design = "Thiết kế ngoại thất rất đẹp, nội thất sang trọng, mình rất hài lòng"
        keywords_design: List[Dict[str, object]] = [
            {"keyword": "thiết kế", "aspect": "DESIGN", "position": text_design.lower().find("thiết kế")}
        ]

        result_design = analyzer.analyze(text_design, keywords_design)
        design = result_design["aspects"].get("DESIGN")
        assert design is not None
        assert design["label"] == "POSITIVE"
        assert design["score"] > 0

        # SERVICE praise
        text_service = "Dịch vụ bảo hành và chăm sóc khách hàng cực kỳ tốt, nhân viên nhiệt tình"
        keywords_service: List[Dict[str, object]] = [
            {"keyword": "dịch vụ", "aspect": "SERVICE", "position": text_service.lower().find("dịch vụ")}
        ]

        result_service = analyzer.analyze(text_service, keywords_service)
        service = result_service["aspects"].get("SERVICE")
        assert service is not None
        assert service["label"] == "POSITIVE"
        assert service["score"] > 0

    def test_semantic_correctness_negative_aspects(self, analyzer: SentimentAnalyzer) -> None:
        """Negative-only examples for price and quality should be NEGATIVE."""
        # PRICE complaint
        text_price = "Giá quá cao, rất đắt so với chất lượng, hoàn toàn không xứng đáng"
        keywords_price: List[Dict[str, object]] = [
            {"keyword": "giá", "aspect": "PRICE", "position": text_price.lower().find("giá")}
        ]

        result_price = analyzer.analyze(text_price, keywords_price)
        price = result_price["aspects"].get("PRICE")
        assert price is not None
        assert price["label"] == "NEGATIVE"
        assert price["score"] < 0
        assert result_price["overall"]["label"] == "NEGATIVE"
        assert result_price["overall"]["score"] < 0

        # PERFORMANCE / quality complaint
        text_quality = "Chất lượng kém, xe chạy ồn, hay hỏng vặt, trải nghiệm rất tệ"
        keywords_quality: List[Dict[str, object]] = [
            {"keyword": "chất lượng", "aspect": "PERFORMANCE", "position": text_quality.lower().find("chất lượng")}
        ]

        result_quality = analyzer.analyze(text_quality, keywords_quality)
        perf = result_quality["aspects"].get("PERFORMANCE")
        assert perf is not None
        assert perf["label"] == "NEGATIVE"
        assert perf["score"] < 0
        assert result_quality["overall"]["label"] == "NEGATIVE"
        assert result_quality["overall"]["score"] < 0
