import torch  # type: ignore
import warnings
from pathlib import Path
from typing import Dict, List, Protocol, runtime_checkable

# Suppress numpy deprecation warning from pyvi (happens when loading pickle model)
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", message=".*align.*")
    from pyvi import ViTokenizer  # type: ignore

from transformers import AutoTokenizer  # type: ignore
from optimum.onnxruntime import ORTModelForSequenceClassification  # type: ignore
from .constant import (
    MODEL_FILE_NAME,
    DEFAULT_NEUTRAL_RESPONSE,
    DEFAULT_PROBABILITIES,
    SENTIMENT_INDEX_MAP,
    SENTIMENT_LABELS,
    TENSOR_TYPE_PT,
    PADDING_STRATEGY,
    KEY_INPUT_IDS,
    KEY_ATTENTION_MASK,
    ERROR_MODEL_DIR_NOT_FOUND,
    ERROR_MODEL_FILE_NOT_FOUND,
    ERROR_MODEL_LOAD_FAILED,
)
from .type import PhoBERTConfig, PhobertOnnxOutput, PhobertOnnxProbability


@runtime_checkable
class IPhoBERTONNX(Protocol):
    """Protocol defining the PhoBERT ONNX interface."""

    def predict(
        self, text: str, return_probabilities: bool = True
    ) -> PhobertOnnxOutput:
        """Predict sentiment for a single text."""
        ...

    def predict_batch(
        self, texts: List[str], return_probabilities: bool = True
    ) -> List[PhobertOnnxOutput]:
        """Predict sentiment for multiple texts."""
        ...


class PhoBERTONNX(IPhoBERTONNX):
    """PhoBERT ONNX model wrapper for Vietnamese sentiment analysis.

    This class handles:
    - Text segmentation using PyVi
    - Tokenization using PhoBERT tokenizer
    - ONNX inference for sentiment prediction
    - Post-processing to convert logits to ratings (1-5 stars)

    Attributes:
        config: PhoBERT configuration
        tokenizer: PhoBERT tokenizer instance
        model: ONNX Runtime model instance
    """

    def __init__(self, config: PhoBERTConfig):
        """Initialize PhoBERT ONNX model.

        Args:
            config: PhoBERT configuration

        Raises:
            FileNotFoundError: If model files are not found
            RuntimeError: If model loading fails
        """
        self.config = config
        self.model_path = Path(config.model_path)

        # Validate model path
        if not self.model_path.exists():
            raise FileNotFoundError(
                ERROR_MODEL_DIR_NOT_FOUND.format(path=self.model_path)
            )

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
        """Segment Vietnamese text using PyVi. Always enabled.

        Args:
            text: Raw Vietnamese text

        Returns:
            Segmented text with underscores (e.g., "Sản_phẩm chất_lượng cao")
        """
        if not text or not text.strip():
            return ""
        # Always segment
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
            return_tensors=TENSOR_TYPE_PT,
            truncation=True,
            max_length=self.config.max_length,
            padding=PADDING_STRATEGY,
            add_special_tokens=True,  # Critical: Ensure <s> and </s> tokens are added for PhoBERT
        )
        return inputs

    def _postprocess(
        self, logits: torch.Tensor, return_probabilities: bool = True
    ) -> PhobertOnnxOutput:
        """Post-process model output to get rating and probabilities.

        Args:
            logits: Raw model output logits
            return_probabilities: Whether to include probability distribution

        Returns:
            PhobertOnnxOutput with rating, sentiment label, confidence, and optionally probabilities
        """
        # Convert logits to probabilities
        probs = logits.softmax(dim=1)

        # Get predicted class index
        label_idx = torch.argmax(probs, dim=1).item()

        # Map to sentiment (using index map)
        sentiment_enum = SENTIMENT_INDEX_MAP[label_idx]
        sentiment_label = SENTIMENT_LABELS[sentiment_enum]

        # In the original code, 'rating' seemed to be mapped from the enum value,
        # but here we use the enum value directly as the rating for now (0, 1, 2)
        # or map it if needed. The original code was ambiguous.
        # Assuming rating corresponds to the enum integer value.
        rating = sentiment_enum.value

        # Get confidence score
        confidence = probs[0][label_idx].item()

        probabilities = None
        if return_probabilities:
            # Handle 3-class model output (wonrax model: NEG=0, POS=1, NEU=2)
            probabilities = PhobertOnnxProbability(
                NEGATIVE=probs[0][0].item(),  # Index 0 = NEG
                POSITIVE=probs[0][1].item(),  # Index 1 = POS
                NEUTRAL=probs[0][2].item(),  # Index 2 = NEU
            )

        return PhobertOnnxOutput(
            rating=rating,
            sentiment=sentiment_label,
            confidence=confidence,
            probabilities=probabilities,
            label=sentiment_label,  # Backward compatibility
        )

    def predict(
        self, text: str, return_probabilities: bool = True
    ) -> PhobertOnnxOutput:
        """Predict sentiment for Vietnamese text.

        Args:
            text: Raw Vietnamese text to analyze
            return_probabilities: Whether to include probability distribution

        Returns:
            PhobertOnnxOutput object
        """
        # Handle empty input
        if not text or not text.strip():
            # Return default neutral response
            probs = None
            if return_probabilities:
                probs = PhobertOnnxProbability(
                    NEGATIVE=DEFAULT_PROBABILITIES[0],
                    POSITIVE=DEFAULT_PROBABILITIES[1],
                    NEUTRAL=DEFAULT_PROBABILITIES[2],
                )

            return PhobertOnnxOutput(
                rating=2,  # Neutral
                sentiment="Trung tính",
                confidence=1.0,
                probabilities=probs,
                label="Trung tính",
            )

        # 1. Segment text (always enabled)
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
        self, texts: List[str], return_probabilities: bool = True
    ) -> List[PhobertOnnxOutput]:
        """Predict sentiment for multiple texts.

        Args:
            texts: List of Vietnamese texts to analyze
            return_probabilities: Whether to include probability distribution

        Returns:
            List of PhobertOnnxOutput objects
        """
        return [self.predict(text, return_probabilities) for text in texts]


__all__ = [
    "PhoBERTConfig",
    "PhoBERTONNX",
    "IPhoBERTONNX",
]
