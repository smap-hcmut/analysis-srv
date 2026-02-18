from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from .type import BuildInput, BuildOutput


@runtime_checkable
class IResultBuilderUseCase(Protocol):
    def build(self, input_data: "BuildInput") -> "BuildOutput":
        ...


__all__ = ["IResultBuilderUseCase"]
