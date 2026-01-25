"""PhoBERT ONNX Wrapper for Sentiment Analysis.

This module provides a high-performance wrapper for the PhoBERT ONNX model
to predict sentiment from Vietnamese text (5-class: 1-5 stars).
"""

import torch  # type: ignore
from pathlib import Path
from typing import Dict, Any
from pyvi import ViTokenizer  # type: ignore
from transformers import AutoTokenizer  # type: ignore
from optimum.onnxruntime import ORTModelForSequenceClassification  # type: ignore

from infrastructure.ai.constants import (
    DEFAULT_MODEL_PATH,
    DEFAULT_MAX_LENGTH,
    MODEL_FILE_NAME,
    SENTIMENT_MAP,
    SENTIMENT_LABELS,
    DEFAULT_NEUTRAL_RESPONSE,
    DEFAULT_PROBABILITIES,
    ERROR_MODEL_DIR_NOT_FOUND,
    ERROR_MODEL_FILE_NOT_FOUND,
    ERROR_MODEL_LOAD_FAILED,
)


class PhoBERTONNX:
    """PhoBERT ONNX model wrapper for Vietnamese sentiment analysis.

    This class handles:
    - Text segmentation using PyVi
    - Tokenization using PhoBERT tokenizer
    - ONNX inference for sentiment prediction
    - Post-processing to convert logits to ratings (1-5 stars)

    Attributes:
        model_path: Path to the directory containing ONNX model files
        tokenizer: PhoBERT tokenizer instance
        model: ONNX Runtime model instance
        max_length: Maximum sequence length (default: 128)
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, max_length: int = DEFAULT_MAX_LENGTH):
        """Initialize PhoBERT ONNX model.

        Args:
            model_path: Path to directory containing model_quantized.onnx and tokenizer files
            max_length: Maximum sequence length for tokenization

        Raises:
            FileNotFoundError: If model files are not found
            RuntimeError: If model loading fails
        """
        self.model_path = Path(model_path)
        self.max_length = max_length

        # Validate model path
        if not self.model_path.exists():
            raise FileNotFoundError(ERROR_MODEL_DIR_NOT_FOUND.format(path=self.model_path))

        model_file = self.model_path / MODEL_FILE_NAME
        if not model_file.exists():
            raise FileNotFoundError(ERROR_MODEL_FILE_NOT_FOUND.format(path=model_file))

        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))

            # Load ONNX model
            self.model = ORTModelForSequenceClassification.from_pretrained(
                str(self.model_path), file_name=MODEL_FILE_NAME
            )
        except Exception as e:
            raise RuntimeError(ERROR_MODEL_LOAD_FAILED.format(error=e))

    def _segment_text(self, text: str) -> str:
        """Segment Vietnamese text using PyVi.

        Args:
            text: Raw Vietnamese text

        Returns:
            Segmented text with underscores (e.g., "Sản_phẩm chất_lượng cao")
        """
        if not text or not text.strip():
            return ""

        return ViTokenizer.tokenize(text)

    def _tokenize(self, text: str) -> Dict[str, torch.Tensor]:
        """Tokenize segmented text.

        Args:
            text: Segmented Vietnamese text

        Returns:
            Dictionary containing input_ids and attention_mask tensors
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            add_special_tokens=True,  # Critical: Ensure <s> and </s> tokens are added for PhoBERT
        )
        return inputs

    def _postprocess(
        self, logits: torch.Tensor, return_probabilities: bool = True
    ) -> Dict[str, Any]:
        """Post-process model output to get rating and probabilities.

        Args:
            logits: Raw model output logits
            return_probabilities: Whether to include probability distribution

        Returns:
            Dictionary with rating, sentiment label, confidence, and optionally probabilities
        """
        # Convert logits to probabilities
        probs = logits.softmax(dim=1)

        # Get predicted class index
        label_idx = torch.argmax(probs, dim=1).item()

        # Map to rating (1-5)
        rating = SENTIMENT_MAP[label_idx]
        sentiment = SENTIMENT_LABELS[rating]

        # Get confidence score
        confidence = probs[0][label_idx].item()

        result = {
            "rating": rating,
            "sentiment": sentiment,
            "label": sentiment,  # Alias for backward compatibility with example code
            "confidence": confidence,
        }

        if return_probabilities:
            # Handle 3-class model output (wonrax model: NEG=0, POS=1, NEU=2)
            result["probabilities"] = {
                "NEGATIVE": probs[0][0].item(),  # Index 0 = NEG
                "POSITIVE": probs[0][1].item(),  # Index 1 = POS
                "NEUTRAL": probs[0][2].item(),   # Index 2 = NEU
            }

        return result

    def predict(self, text: str, return_probabilities: bool = True) -> Dict[str, Any]:
        """Predict sentiment for Vietnamese text.

        Args:
            text: Raw Vietnamese text to analyze
            return_probabilities: Whether to include probability distribution

        Returns:
            Dictionary containing:
                - rating (int): 1-5 star rating
                - sentiment (str): Sentiment label (VERY_NEGATIVE to VERY_POSITIVE)
                - confidence (float): Confidence score (0-1)
                - probabilities (dict, optional): Probability for each class

        Example:
            >>> model = PhoBERTONNX()
            >>> result = model.predict("Sản phẩm chất lượng cao")
            >>> print(result)
            {
                'rating': 4,
                'sentiment': 'POSITIVE',
                'confidence': 0.92,
                'probabilities': {
                    'NEGATIVE': 0.02,
                    'NEUTRAL': 0.06,
                    'POSITIVE': 0.92
                }
            }
        """
        # Handle empty input
        if not text or not text.strip():
            result = DEFAULT_NEUTRAL_RESPONSE.copy()
            if return_probabilities:
                result["probabilities"] = DEFAULT_PROBABILITIES.copy()
            return result

        # 1. Segment text
        segmented_text = self._segment_text(text)

        # 2. Tokenize
        inputs = self._tokenize(segmented_text)

        # 3. Inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # 4. Post-process
        result = self._postprocess(outputs.logits, return_probabilities)

        return result

    def predict_batch(
        self, texts: list[str], return_probabilities: bool = True
    ) -> list[Dict[str, Any]]:
        """Predict sentiment for multiple texts.

        Args:
            texts: List of Vietnamese texts to analyze
            return_probabilities: Whether to include probability distribution

        Returns:
            List of prediction dictionaries
        """
        return [self.predict(text, return_probabilities) for text in texts]
