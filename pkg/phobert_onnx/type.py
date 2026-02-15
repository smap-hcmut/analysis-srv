from dataclasses import dataclass, field
from typing import Optional
from .constant import *


@dataclass
class PhoBERTConfig:
    """PhoBERT model configuration.

    Attributes:
        model_path: Path to directory containing ONNX model files
        max_length: Maximum sequence length for tokenization
    """

    model_path: str = DEFAULT_MODEL_PATH
    max_length: int = DEFAULT_MAX_LENGTH

    def __post_init__(self):
        """Validate configuration."""
        if self.max_length <= 0:
            raise ValueError(f"max_length must be positive, got {self.max_length}")

        if self.max_length > MAX_SEQUENCE_LENGTH_LIMIT:
            raise ValueError(
                f"max_length cannot exceed {MAX_SEQUENCE_LENGTH_LIMIT}, got {self.max_length}"
            )


@dataclass
class PhobertOnnxProbability:
    """Probability distribution for sentiment classes."""

    NEGATIVE: float
    POSITIVE: float
    NEUTRAL: float


@dataclass
class PhobertOnnxOutput:
    """Sentiment prediction output."""

    rating: int  # 0, 1, 2 mapping to Enum values
    sentiment: str  # Human readable label
    confidence: float
    probabilities: Optional[PhobertOnnxProbability] = None
    label: str = ""  # Backward compatibility alias

    def __post_init__(self):
        if not self.label:
            self.label = self.sentiment
