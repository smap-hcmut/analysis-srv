from typing import Protocol, runtime_checkable

from .type import Input, Output


@runtime_checkable
class IIntentClassification(Protocol):
    """Protocol for intent classification."""

    def process(self, input_data: Input) -> Output:
        """Process input data and return output."""
        ...


__all__ = ["IIntentClassification"]
