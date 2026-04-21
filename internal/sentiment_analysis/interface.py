from typing import Protocol, runtime_checkable, List

from .type import Input, Output


@runtime_checkable
class ISentimentAnalysisUseCase(Protocol):
    def process(self, input_data: Input) -> Output: ...
    def process_batch(self, input_list: List[Input]) -> List[Output]: ...


__all__ = ["ISentimentAnalysisUseCase"]
