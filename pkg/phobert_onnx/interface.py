"""Interface for PhoBERT ONNX operations."""

from typing import List, Protocol, runtime_checkable

from .type import PhobertOnnxOutput


@runtime_checkable
class IPhoBERTONNX(Protocol):
    """Protocol for PhoBERT ONNX sentiment inference."""

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


__all__ = ["IPhoBERTONNX"]
