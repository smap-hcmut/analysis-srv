"""Comprehensive tests for PhoBERT ONNX wrapper."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # type: ignore
import torch  # type: ignore
from unittest.mock import Mock, patch

from infrastructure.ai.phobert_onnx import PhoBERTONNX


class TestSegmentation:
    """Test Vietnamese text segmentation."""

    def test_segment_vietnamese_text(self):
        """Test segmentation with Vietnamese text."""
        with patch("infrastructure.ai.phobert_onnx.ViTokenizer") as mock_vi:
            mock_vi.tokenize.return_value = "Sản_phẩm chất_lượng cao"

            # Create a mock PhoBERT instance
            with (
                patch("infrastructure.ai.phobert_onnx.AutoTokenizer"),
                patch("infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"),
            ):

                # Create temporary model directory
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    model_dir = Path(tmpdir) / "models"
                    model_dir.mkdir()
                    (model_dir / "model_quantized.onnx").touch()
                    (model_dir / "config.json").write_text("{}")

                    phobert = PhoBERTONNX(model_path=str(model_dir))
                    result = phobert._segment_text("Sản phẩm chất lượng cao")

                    assert result == "Sản_phẩm chất_lượng cao"
                    mock_vi.tokenize.assert_called_once_with("Sản phẩm chất lượng cao")

    def test_segment_empty_text(self):
        """Test segmentation with empty text."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer"),
            patch("infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"),
        ):

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))

                assert phobert._segment_text("") == ""
                assert phobert._segment_text("   ") == ""

    def test_segment_special_characters(self):
        """Test segmentation with special characters."""
        with patch("infrastructure.ai.phobert_onnx.ViTokenizer") as mock_vi:
            mock_vi.tokenize.return_value = "Xe đẹp !!! 😊"

            with (
                patch("infrastructure.ai.phobert_onnx.AutoTokenizer"),
                patch("infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"),
            ):

                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    model_dir = Path(tmpdir) / "models"
                    model_dir.mkdir()
                    (model_dir / "model_quantized.onnx").touch()
                    (model_dir / "config.json").write_text("{}")

                    phobert = PhoBERTONNX(model_path=str(model_dir))
                    result = phobert._segment_text("Xe đẹp!!! 😊")

                    assert "đẹp" in result


class TestTokenization:
    """Test tokenization functionality."""

    @pytest.fixture
    def mock_phobert(self):
        """Create a mock PhoBERT instance."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer") as mock_tokenizer,
            patch("infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"),
        ):

            tokenizer_instance = Mock()
            mock_tokenizer.from_pretrained.return_value = tokenizer_instance

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))
                phobert.tokenizer = tokenizer_instance
                yield phobert

    def test_tokenize_text(self, mock_phobert):
        """Test tokenization of text."""
        mock_phobert.tokenizer.return_value = {
            "input_ids": torch.tensor([[1, 2, 3, 4, 5]]),
            "attention_mask": torch.tensor([[1, 1, 1, 1, 1]]),
        }

        result = mock_phobert._tokenize("test text")

        assert "input_ids" in result
        assert "attention_mask" in result
        assert result["input_ids"].shape[1] > 0

    def test_tokenize_max_length(self, mock_phobert):
        """Test tokenization respects max_length."""
        mock_phobert.tokenizer.return_value = {
            "input_ids": torch.randint(0, 1000, (1, 128)),
            "attention_mask": torch.ones((1, 128)),
        }

        result = mock_phobert._tokenize("very long text " * 100)

        # Should be truncated to max_length
        assert result["input_ids"].shape[1] == 128


class TestPostProcessing:
    """Test post-processing of model outputs."""

    @pytest.fixture
    def mock_phobert(self):
        """Create a mock PhoBERT instance."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer"),
            patch("infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"),
        ):

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))
                yield phobert

    def test_postprocess_negative(self, mock_phobert):
        """Test post-processing for NEGATIVE sentiment (3-class model, index 0).

        SENTIMENT_MAP: NEG (index 0) -> 1 star (VERY_NEGATIVE)
        """
        logits = torch.tensor([[5.0, 0.1, 0.1]])  # wonrax model: NEG=0, POS=1, NEU=2
        result = mock_phobert._postprocess(logits)

        assert result["rating"] == 1  # NEG -> 1 star (VERY_NEGATIVE)
        assert result["sentiment"] == "VERY_NEGATIVE"
        assert result["confidence"] > 0.9

    def test_postprocess_positive(self, mock_phobert):
        """Test post-processing for POSITIVE sentiment (3-class model, index 1).

        SENTIMENT_MAP: POS (index 1) -> 5 stars (VERY_POSITIVE)
        """
        logits = torch.tensor([[0.1, 5.0, 0.1]])  # wonrax model: NEG=0, POS=1, NEU=2
        result = mock_phobert._postprocess(logits)

        assert result["rating"] == 5  # POS -> 5 stars (VERY_POSITIVE)
        assert result["sentiment"] == "VERY_POSITIVE"
        assert result["confidence"] > 0.9

    def test_postprocess_neutral(self, mock_phobert):
        """Test post-processing for NEUTRAL sentiment (3-class model, index 2)."""
        logits = torch.tensor([[0.1, 0.1, 5.0]])  # wonrax model: NEG=0, POS=1, NEU=2
        result = mock_phobert._postprocess(logits)

        assert result["rating"] == 3
        assert result["sentiment"] == "NEUTRAL"
        assert result["confidence"] > 0.9

    def test_postprocess_all_label_indices(self, mock_phobert):
        """Test that all label indices (0, 1, 2) map to correct ratings and labels.

        SENTIMENT_MAP from constants.py:
        - NEG (index 0) -> 1 star (VERY_NEGATIVE)
        - POS (index 1) -> 5 stars (VERY_POSITIVE)
        - NEU (index 2) -> 3 stars (NEUTRAL)
        """
        # wonrax model mapping: 0=NEG, 1=POS, 2=NEU
        test_cases = [
            (torch.tensor([[10.0, 0.0, 0.0]]), 0, 1, "VERY_NEGATIVE"),  # NEG -> 1 star
            (torch.tensor([[0.0, 10.0, 0.0]]), 1, 5, "VERY_POSITIVE"),  # POS -> 5 stars
            (torch.tensor([[0.0, 0.0, 10.0]]), 2, 3, "NEUTRAL"),  # NEU -> 3 stars
        ]

        for logits, expected_idx, expected_rating, expected_label in test_cases:
            result = mock_phobert._postprocess(logits)
            assert result["rating"] == expected_rating
            assert result["sentiment"] == expected_label
            assert result["confidence"] > 0.99

    def test_postprocess_probabilities(self, mock_phobert):
        """Test post-processing includes probabilities (3-class model)."""
        logits = torch.tensor([[0.1, 0.1, 5.0]])  # 3-class: NEGATIVE, NEUTRAL, POSITIVE
        result = mock_phobert._postprocess(logits, return_probabilities=True)

        assert "probabilities" in result
        assert len(result["probabilities"]) == 3
        assert "NEGATIVE" in result["probabilities"]
        assert "NEUTRAL" in result["probabilities"]
        assert "POSITIVE" in result["probabilities"]
        assert sum(result["probabilities"].values()) == pytest.approx(1.0, rel=0.01)

    def test_postprocess_probability_sum(self, mock_phobert):
        """Test that probability distribution sums to ~1.0 for all classes."""
        test_cases = [
            torch.tensor([[2.0, 1.0, 0.5]]),
            torch.tensor([[0.5, 2.0, 1.0]]),
            torch.tensor([[1.0, 0.5, 2.0]]),
            torch.tensor([[1.0, 1.0, 1.0]]),  # Uniform
        ]

        for logits in test_cases:
            result = mock_phobert._postprocess(logits, return_probabilities=True)
            prob_sum = sum(result["probabilities"].values())
            assert prob_sum == pytest.approx(1.0, abs=0.001)

    def test_postprocess_without_probabilities(self, mock_phobert):
        """Test post-processing without probabilities (3-class model)."""
        logits = torch.tensor([[0.1, 0.1, 5.0]])  # 3-class: NEGATIVE, NEUTRAL, POSITIVE
        result = mock_phobert._postprocess(logits, return_probabilities=False)

        assert "probabilities" not in result
        assert "rating" in result
        assert "sentiment" in result
        assert "confidence" in result


class TestPrediction:
    """Test prediction functionality."""

    @pytest.fixture
    def mock_phobert(self):
        """Create a mock PhoBERT instance with mocked model."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer") as mock_tokenizer,
            patch(
                "infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"
            ) as mock_model_class,
        ):

            tokenizer_instance = Mock()
            tokenizer_instance.return_value = {
                "input_ids": torch.randint(0, 1000, (1, 128)),
                "attention_mask": torch.ones((1, 128)),
            }
            mock_tokenizer.from_pretrained.return_value = tokenizer_instance

            model_instance = Mock()
            mock_model_class.from_pretrained.return_value = model_instance

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))
                phobert.model = model_instance
                phobert.tokenizer = tokenizer_instance
                yield phobert

    def test_predict_positive(self, mock_phobert):
        """Test prediction for positive sentiment (3-class model).

        SENTIMENT_MAP: POS (index 1) -> 5 stars (VERY_POSITIVE)
        """
        mock_output = Mock()
        mock_output.logits = torch.tensor([[0.1, 5.0, 0.1]])  # wonrax model: NEG=0, POS=1, NEU=2
        mock_phobert.model.return_value = mock_output

        result = mock_phobert.predict("Sản phẩm tuyệt vời!")

        assert result["rating"] == 5  # POS -> 5 stars (VERY_POSITIVE)
        assert result["sentiment"] == "VERY_POSITIVE"
        assert result["confidence"] > 0.5

    def test_predict_negative(self, mock_phobert):
        """Test prediction for negative sentiment (3-class model).

        SENTIMENT_MAP: NEG (index 0) -> 1 star (VERY_NEGATIVE)
        """
        mock_output = Mock()
        mock_output.logits = torch.tensor([[5.0, 0.1, 0.1]])  # wonrax model: NEG=0, POS=1, NEU=2
        mock_phobert.model.return_value = mock_output

        result = mock_phobert.predict("Sản phẩm tệ!")

        assert result["rating"] == 1  # NEG -> 1 star (VERY_NEGATIVE)
        assert result["sentiment"] == "VERY_NEGATIVE"

    def test_predict_empty_text(self, mock_phobert):
        """Test prediction with empty text."""
        result = mock_phobert.predict("")

        assert result["rating"] == 3
        assert result["sentiment"] == "NEUTRAL"
        assert result["confidence"] == 0.0

    def test_predict_long_text(self, mock_phobert):
        """Test prediction with very long text (3-class model)."""
        mock_output = Mock()
        mock_output.logits = torch.tensor([[0.1, 0.1, 5.0]])  # wonrax model: NEG=0, POS=1, NEU=2
        mock_phobert.model.return_value = mock_output

        long_text = "Sản phẩm này " * 200  # Very long text
        result = mock_phobert.predict(long_text)

        assert result["rating"] in [2, 3, 4]  # 3-class maps to ratings 2, 3, 4
        assert result["sentiment"] in [
            "NEGATIVE",
            "NEUTRAL",
            "POSITIVE",
        ]


class TestBatchPrediction:
    """Test batch prediction functionality."""

    @pytest.fixture
    def mock_phobert(self):
        """Create a mock PhoBERT instance."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer") as mock_tokenizer,
            patch(
                "infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"
            ) as mock_model_class,
        ):

            tokenizer_instance = Mock()
            tokenizer_instance.return_value = {
                "input_ids": torch.randint(0, 1000, (1, 128)),
                "attention_mask": torch.ones((1, 128)),
            }
            mock_tokenizer.from_pretrained.return_value = tokenizer_instance

            model_instance = Mock()
            mock_model_class.from_pretrained.return_value = model_instance

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))
                phobert.model = model_instance
                phobert.tokenizer = tokenizer_instance
                yield phobert

    def test_predict_batch(self, mock_phobert):
        """Test batch prediction (3-class model)."""
        # Mock different outputs for each call
        # wonrax model: NEG=0, POS=1, NEU=2
        outputs = [
            Mock(logits=torch.tensor([[0.1, 5.0, 0.1]])),  # POS (index 1)
            Mock(logits=torch.tensor([[5.0, 0.1, 0.1]])),  # NEG (index 0)
            Mock(logits=torch.tensor([[0.1, 0.1, 5.0]])),  # NEU (index 2)
        ]
        mock_phobert.model.side_effect = outputs

        texts = ["Sản phẩm tuyệt vời!", "Sản phẩm tệ!", "Sản phẩm bình thường"]

        results = mock_phobert.predict_batch(texts)

        assert len(results) == 3
        assert results[0]["rating"] == 5  # POS -> 5 stars
        assert results[1]["rating"] == 1  # NEG -> 1 star
        assert results[2]["rating"] == 3  # NEU -> 3 stars

    def test_predict_batch_empty_list(self, mock_phobert):
        """Test batch prediction with empty list."""
        results = mock_phobert.predict_batch([])
        assert len(results) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_init_nonexistent_path(self):
        """Test initialization with non-existent path."""
        with pytest.raises(FileNotFoundError, match="Model directory not found"):
            PhoBERTONNX(model_path="/nonexistent/path")

    def test_init_missing_model_file(self):
        """Test initialization with missing model file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            model_dir.mkdir()

            with pytest.raises(FileNotFoundError, match="Model file not found"):
                PhoBERTONNX(model_path=str(model_dir))

    def test_predict_special_characters(self):
        """Test prediction with special characters (3-class model)."""
        with (
            patch("infrastructure.ai.phobert_onnx.AutoTokenizer") as mock_tokenizer,
            patch(
                "infrastructure.ai.phobert_onnx.ORTModelForSequenceClassification"
            ) as mock_model_class,
        ):

            tokenizer_instance = Mock()
            tokenizer_instance.return_value = {
                "input_ids": torch.randint(0, 1000, (1, 128)),
                "attention_mask": torch.ones((1, 128)),
            }
            mock_tokenizer.from_pretrained.return_value = tokenizer_instance

            model_instance = Mock()
            mock_output = Mock()
            mock_output.logits = torch.tensor(
                [[0.1, 5.0, 0.1]]
            )  # wonrax model: NEG=0, POS=1, NEU=2
            model_instance.return_value = mock_output
            mock_model_class.from_pretrained.return_value = model_instance

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                model_dir = Path(tmpdir) / "models"
                model_dir.mkdir()
                (model_dir / "model_quantized.onnx").touch()
                (model_dir / "config.json").write_text("{}")

                phobert = PhoBERTONNX(model_path=str(model_dir))
                phobert.model = model_instance
                phobert.tokenizer = tokenizer_instance

                result = phobert.predict("Xe đẹp!!! 😊 @#$%")

                assert result["rating"] in [1, 3, 5]  # 3-class maps to ratings 1, 3, 5
