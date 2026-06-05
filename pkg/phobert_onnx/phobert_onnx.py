import os
import numpy as np
import logging
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, List

# analysis-consumer only uses Transformers for tokenizer + ONNXRuntime.
# Forcing USE_TORCH=0 avoids importing the heavyweight torch runtime on nodes
# where it is unstable, while preserving the tokenizer/Optimum code path.
os.environ.setdefault("USE_TORCH", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("onnxruntime").setLevel(logging.ERROR)

# Suppress numpy deprecation warning from pyvi (happens when loading pickle model)
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", message=".*align.*")
    with open(os.devnull, "w") as _devnull:
        with redirect_stdout(_devnull), redirect_stderr(_devnull):
            from pyvi import ViTokenizer  # type: ignore
            from transformers import AutoTokenizer  # type: ignore

from onnxruntime import InferenceSession, SessionOptions  # type: ignore
from .interface import IPhoBERTONNX
from .constant import (
    MODEL_FILE_NAME,
    DEFAULT_PROBABILITIES,
    SENTIMENT_INDEX_MAP,
    SENTIMENT_LABELS,
    PADDING_STRATEGY,
    ERROR_MODEL_DIR_NOT_FOUND,
    ERROR_MODEL_FILE_NOT_FOUND,
    ERROR_MODEL_LOAD_FAILED,
)
from .type import PhoBERTConfig, PhobertOnnxOutput, PhobertOnnxProbability


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

            session_options = SessionOptions()
            session_options.intra_op_num_threads = config.intra_op_num_threads
            session_options.inter_op_num_threads = config.inter_op_num_threads

            # Load ONNX model directly to avoid Optimum's heavier import chain.
            self.model = InferenceSession(
                str(model_file),
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
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

    def _tokenize(self, text: str) -> Dict[str, Any]:
        """Tokenize segmented text.

        Args:
            text: Segmented Vietnamese text

        Returns:
            Dictionary containing input_ids and attention_mask tensors
        """
        inputs = self.tokenizer(
            text,
            return_tensors="np",
            truncation=True,
            max_length=self.config.max_length,
            padding=PADDING_STRATEGY,
            add_special_tokens=True,  # Critical: Ensure <s> and </s> tokens are added for PhoBERT
        )
        return {
            key: value
            for key, value in inputs.items()
            if key in {"input_ids", "attention_mask"}
        }

    def _postprocess(self, logits: Any, return_probabilities: bool = True) -> PhobertOnnxOutput:
        """Post-process model output to get rating and probabilities.

        Args:
            logits: Raw model output logits
            return_probabilities: Whether to include probability distribution

        Returns:
            PhobertOnnxOutput with rating, sentiment label, confidence, and optionally probabilities
        """
        # Convert logits to probabilities
        logits_arr = np.asarray(logits, dtype=np.float32)
        shifted = logits_arr - np.max(logits_arr, axis=1, keepdims=True)
        probs = np.exp(shifted)
        probs = probs / np.sum(probs, axis=1, keepdims=True)

        # Get predicted class index
        label_idx = int(np.argmax(probs, axis=1)[0])

        # Map to sentiment (using index map)
        sentiment_enum = SENTIMENT_INDEX_MAP[label_idx]
        sentiment_label = SENTIMENT_LABELS[sentiment_enum]

        # In the original code, 'rating' seemed to be mapped from the enum value,
        # but here we use the enum value directly as the rating for now (0, 1, 2)
        # or map it if needed. The original code was ambiguous.
        # Assuming rating corresponds to the enum integer value.
        rating = sentiment_enum.value

        # Get confidence score
        confidence = float(probs[0][label_idx])

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
        outputs = self.model.run(None, dict(inputs))

        # 4. Post-process
        result = self._postprocess(outputs[0], return_probabilities)

        return result

    def predict_batch(
        self, texts: List[str], return_probabilities: bool = True
    ) -> List[PhobertOnnxOutput]:
        """Predict sentiment for multiple texts in a single ONNX call.

        Empty texts receive a default neutral result immediately.
        All non-empty texts are segmented, batch-tokenized, and run through
        the ONNX runtime in one forward pass before per-row post-processing.

        Args:
            texts: List of raw Vietnamese texts to analyze
            return_probabilities: Whether to include probability distribution

        Returns:
            List of PhobertOnnxOutput objects, one per input text
        """
        if not texts:
            return []

        results: List[PhobertOnnxOutput] = [None] * len(texts)  # type: ignore[list-item]
        unique_positions: Dict[str, int] = {}
        unique_segmented: List[str] = []
        text_to_indices: Dict[str, List[int]] = {}

        # Assign default neutral for empty inputs; segment the rest.
        for i, text in enumerate(texts):
            if not text or not text.strip():
                probs = None
                if return_probabilities:
                    probs = PhobertOnnxProbability(
                        NEGATIVE=DEFAULT_PROBABILITIES[0],
                        POSITIVE=DEFAULT_PROBABILITIES[1],
                        NEUTRAL=DEFAULT_PROBABILITIES[2],
                    )
                results[i] = PhobertOnnxOutput(
                    rating=2,
                    sentiment="Trung tính",
                    confidence=1.0,
                    probabilities=probs,
                    label="Trung tính",
                )
            else:
                text_to_indices.setdefault(text, []).append(i)
                if text not in unique_positions:
                    unique_positions[text] = len(unique_segmented)
                    unique_segmented.append(self._segment_text(text))

        if not unique_segmented:
            return results

        # Batch tokenize — padding=True pads all sequences to the longest
        # in the batch so they form a rectangular tensor.
        inputs = self.tokenizer(
            unique_segmented,
            return_tensors="np",
            truncation=True,
            max_length=self.config.max_length,
            padding=True,
            add_special_tokens=True,
        )
        inputs = {
            key: value
            for key, value in inputs.items()
            if key in {"input_ids", "attention_mask"}
        }

        # Single ONNX inference call for the entire batch.
        outputs = self.model.run(None, dict(inputs))

        # outputs.logits shape: [N, num_classes]
        logits_arr = np.asarray(outputs[0], dtype=np.float32)
        shifted = logits_arr - np.max(logits_arr, axis=1, keepdims=True)
        batch_probs = np.exp(shifted)
        batch_probs = batch_probs / np.sum(batch_probs, axis=1, keepdims=True)

        unique_results: List[PhobertOnnxOutput] = [None] * len(unique_segmented)  # type: ignore[list-item]

        for batch_idx in range(len(unique_segmented)):
            probs = batch_probs[batch_idx]  # shape [num_classes]
            label_idx = int(np.argmax(probs))

            sentiment_enum = SENTIMENT_INDEX_MAP[label_idx]
            sentiment_label = SENTIMENT_LABELS[sentiment_enum]
            rating = sentiment_enum.value
            confidence = float(probs[label_idx])

            probabilities = None
            if return_probabilities:
                probabilities = PhobertOnnxProbability(
                    NEGATIVE=float(probs[0]),
                    POSITIVE=float(probs[1]),
                    NEUTRAL=float(probs[2]),
                )

            unique_results[batch_idx] = PhobertOnnxOutput(
                rating=rating,
                sentiment=sentiment_label,
                confidence=confidence,
                probabilities=probabilities,
                label=sentiment_label,
            )

        for text, indices in text_to_indices.items():
            unique_result = unique_results[unique_positions[text]]
            for orig_idx in indices:
                results[orig_idx] = unique_result

        return results


__all__ = [
    "PhoBERTConfig",
    "PhoBERTONNX",
]
