"""Enrichment interface — Protocol for EnrichmentUseCase."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from internal.enrichment.type import EnrichmentInput, EnrichmentOutput


@runtime_checkable
class IEnrichmentUseCase(Protocol):
    def enrich(self, inp: "EnrichmentInput") -> "EnrichmentOutput":
        """Run enrichment pipeline on a batch of mentions."""
        ...
