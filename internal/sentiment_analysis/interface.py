from typing import Protocol, runtime_checkable

from .type import Input, Output


@runtime_checkable
class ISentimentAnalysis(Protocol):
    """Protocol for sentiment analysis."""

    def process(self, input_data: Input) -> Output:
        """Process input data and return output."""
        ...


__all__ = ["ISentimentAnalysis"]
