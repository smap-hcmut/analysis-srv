from typing import Protocol, runtime_checkable

from .type import RunContext


@runtime_checkable
class IRunContextBuilder(Protocol):
    """Builds a RunContext for a batch run."""

    def build(self, project_id: str, **kwargs) -> RunContext: ...


__all__ = ["IRunContextBuilder"]
