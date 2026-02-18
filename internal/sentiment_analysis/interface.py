from typing import Protocol, runtime_checkable

from .type import Input, Output


@runtime_checkable
class ISentimentAnalysisUseCase(Protocol):
    def process(self, input_data: Input) -> Output: ...


__all__ = ["ISentimentAnalysisUseCase"]
