from typing import Protocol, runtime_checkable

from .type import Input, Output


@runtime_checkable
class ITextProcessing(Protocol):
    """Protocol for text preprocessing."""
    
    def process(self, input_data: Input) -> Output:
        """Process input data and return output."""
        ...


__all__ = ["ITextProcessing"]
