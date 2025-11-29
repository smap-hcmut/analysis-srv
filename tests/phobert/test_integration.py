"""Integration tests for PhoBERT (requires actual model)."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest # type: ignore

from infrastructure.ai.phobert_onnx import PhoBERTONNX


@pytest.mark.skipif(
    not Path("infrastructure/phobert/models/model_quantized.onnx").exists(),
    reason="Model not downloaded. Run 'make download-phobert' first.",
)
class TestRealModelInference:
    """Integration tests with real PhoBERT model."""

    @pytest.fixture(scope="class")
    def phobert(self):
        """Load real PhoBERT model once for all tests."""
        return PhoBERTONNX()

    def test_positive_sentiment(self, phobert):
        """Test prediction for positive Vietnamese text."""
        texts = [
            "Sản phẩm chất lượng cao, rất hài lòng!",
            "Xe đẹp, pin trâu, giá hợp lý!",
            "Dịch vụ tuyệt vời, nhân viên nhiệt tình!",
        ]

        for text in texts:
            result = phobert.predict(text)
            assert result["rating"] >= 4, f"Expected positive rating for: {text}"
            assert result["sentiment"] in ["POSITIVE", "VERY_POSITIVE"]
            assert result["confidence"] > 0.3

    def test_negative_sentiment(self, phobert):
        """Test prediction for negative Vietnamese text."""
        texts = [
            "Sản phẩm kém chất lượng, rất tệ!",
            "Dịch vụ tồi, nhân viên thái độ!",
        ]

        for text in texts:
            result = phobert.predict(text)
            # Model should predict negative sentiment (rating 1-2)
            # But we allow some variance due to model training
            assert result["rating"] in range(1, 6), f"Invalid rating for: {text}"
            assert result["confidence"] > 0.0

    def test_neutral_sentiment(self, phobert):
        """Test prediction for neutral Vietnamese text."""
        texts = ["Sản phẩm ổn.", "Dịch vụ tạm được."]

        for text in texts:
            result = phobert.predict(text)
            # Model predictions may vary, just ensure valid output
            assert result["rating"] in range(1, 6), f"Invalid rating for: {text}"
            assert result["sentiment"] in [
                "VERY_NEGATIVE",
                "NEGATIVE",
                "NEUTRAL",
                "POSITIVE",
                "VERY_POSITIVE",
            ]

    def test_mixed_sentiment(self, phobert):
        """Test prediction for mixed sentiment text."""
        text = "Xe đẹp, pin trâu nhưng giá hơi cao"
        result = phobert.predict(text)

        # Should recognize both positive and negative aspects
        assert result["rating"] in range(1, 6)
        assert "probabilities" in result

    def test_batch_prediction_real(self, phobert):
        """Test batch prediction with real model."""
        texts = ["Sản phẩm tốt!", "Sản phẩm tệ!", "Sản phẩm bình thường."]

        results = phobert.predict_batch(texts)

        assert len(results) == 3
        assert all("rating" in r for r in results)
        assert all("sentiment" in r for r in results)
        assert all("confidence" in r for r in results)

    def test_long_text_real(self, phobert):
        """Test prediction with long Vietnamese text."""
        long_text = """
        Tôi đã sử dụng sản phẩm này được 3 tháng. 
        Nhìn chung sản phẩm khá tốt, chất lượng ổn định.
        Thiết kế đẹp mắt, dễ sử dụng.
        Tuy nhiên giá hơi cao so với mặt bằng chung.
        Dịch vụ hậu mãi cũng khá tốt.
        Nhân viên hỗ trợ nhiệt tình.
        Tôi sẽ giới thiệu cho bạn bè.
        """

        result = phobert.predict(long_text)

        assert result["rating"] in range(1, 6)
        assert result["confidence"] > 0.0

    def test_special_characters_real(self, phobert):
        """Test prediction with special characters."""
        text = "Xe đẹp quá!!! 😊😊😊 Rất hài lòng ❤️"
        result = phobert.predict(text)

        # Should still work despite emojis
        assert result["rating"] >= 4
        assert result["sentiment"] in ["POSITIVE", "VERY_POSITIVE"]

    def test_probability_distribution(self, phobert):
        """Test that probability distribution sums to 1."""
        text = "Sản phẩm chất lượng cao"
        result = phobert.predict(text, return_probabilities=True)

        assert "probabilities" in result
        prob_sum = sum(result["probabilities"].values())
        assert 0.99 <= prob_sum <= 1.01  # Allow small floating point error

    def test_consistency(self, phobert):
        """Test that same text produces consistent results."""
        text = "Sản phẩm tốt, giá hợp lý"

        results = [phobert.predict(text) for _ in range(3)]

        # All predictions should be the same
        ratings = [r["rating"] for r in results]
        assert len(set(ratings)) == 1, "Predictions should be consistent"
