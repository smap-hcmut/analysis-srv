from typing import Protocol, runtime_checkable
from .type import Input, Output


@runtime_checkable
class IImpactCalculationUseCase(Protocol):
    def process(self, input_data: Input) -> Output: ...


__all__ = ["IImpactCalculationUseCase"]
