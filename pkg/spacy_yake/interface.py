"""Interface for SpaCy-YAKE keyword extraction."""

from typing import List, Protocol, runtime_checkable

from .type import SpacyYakeOutput


@runtime_checkable
class ISpacyYake(Protocol):
    """Protocol for keyword extraction operations."""

    def extract(self, text: str) -> SpacyYakeOutput:
        """Extract keywords from a single text."""
        ...

    def extract_batch(self, texts: List[str]) -> List[SpacyYakeOutput]:
        """Extract keywords from multiple texts."""
        ...


__all__ = ["ISpacyYake"]
