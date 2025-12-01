"""Performance tests for SentimentAnalyzer (ABSA)."""

import time
from pathlib import Path
from typing import Dict, List

import pytest  # type: ignore

from infrastructure.ai.phobert_onnx import PhoBERTONNX
from services.analytics.sentiment import SentimentAnalyzer


@pytest.mark.skipif(
    not Path("infrastructure/phobert/models/model_quantized.onnx").exists(),
    reason="PhoBERT model not downloaded. Run 'make download-phobert' first.",
)
class TestSentimentAnalyzerPerformance:
    """Performance benchmarks for SentimentAnalyzer."""

    @pytest.fixture(scope="class")
    def analyzer(self) -> SentimentAnalyzer:
        """Load PhoBERT model once."""
        phobert = PhoBERTONNX()
        return SentimentAnalyzer(phobert)

    @pytest.fixture
    def sample_text(self) -> str:
        return (
            "Xe VinFast VF3 thiết kế đẹp, nội thất rộng rãi, "
            "nhưng giá hơi cao và pin chưa thực sự tốt."
        )

    @pytest.fixture
    def sample_keywords(self, sample_text: str) -> List[Dict[str, object]]:
        return [
            {"keyword": "thiết kế", "aspect": "DESIGN", "position": sample_text.find("thiết kế")},
            {"keyword": "nội thất", "aspect": "DESIGN", "position": sample_text.find("nội thất")},
            {"keyword": "giá", "aspect": "PRICE", "position": sample_text.find("giá")},
            {"keyword": "pin", "aspect": "PERFORMANCE", "position": sample_text.find("pin")},
        ]

    def test_overall_sentiment_speed(self, analyzer: SentimentAnalyzer, sample_text: str) -> None:
        """Overall sentiment should be computed within 100ms."""
        start = time.time()
        result = analyzer.analyze(sample_text, keywords=None)
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 100.0, f"Overall sentiment took {duration_ms:.2f}ms (>100ms)"
        assert "overall" in result

    def test_aspect_sentiment_speed(
        self,
        analyzer: SentimentAnalyzer,
        sample_text: str,
        sample_keywords: List[Dict[str, object]],
    ) -> None:
        """Aspect-based sentiment for 3-4 aspects should finish within 500ms."""
        start = time.time()
        result = analyzer.analyze(sample_text, keywords=sample_keywords)
        duration_ms = (time.time() - start) * 1000

        assert duration_ms < 500.0, f"ABSA analysis took {duration_ms:.2f}ms (>500ms)"
        assert "aspects" in result
        assert len(result["aspects"]) >= 2

    def test_batch_posts_throughput(self, analyzer: SentimentAnalyzer) -> None:
        """Benchmark throughput on a small batch of posts."""
        texts = [
            "Xe thiết kế đẹp nhưng giá cao",
            "Pin yếu, sạc lâu nhưng dịch vụ tốt",
            "Giá rẻ, thiết kế bình thường, chất lượng ổn",
        ] * 5  # 15 posts

        keywords_list: List[List[Dict[str, object]]] = []
        for text in texts:
            kws: List[Dict[str, object]] = []
            if "thiết kế" in text:
                kws.append(
                    {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")}
                )
            if "giá" in text:
                kws.append({"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")})
            if "pin" in text:
                kws.append(
                    {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.find("pin")}
                )
            keywords_list.append(kws)

        start = time.time()
        for text, kws in zip(texts, keywords_list):
            analyzer.analyze(text, keywords=kws)
        duration = time.time() - start

        throughput = len(texts) / duration
        # Target: at least 5 posts per second for ABSA (conservative)
        assert throughput >= 5.0, f"Throughput {throughput:.2f} posts/s (<5 posts/s)"
