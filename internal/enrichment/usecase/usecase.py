"""EnrichmentUseCase — implements IEnrichmentUseCase.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from internal.enrichment.interface import IEnrichmentUseCase
from internal.enrichment.type import (
    EnricherConfig,
    EnrichmentInput,
    EnrichmentOutput,
)
from internal.enrichment.usecase.enrich_batch import enrich_batch

if TYPE_CHECKING:
    from internal.ontology.usecase.file_registry import FileOntologyRegistry


class EnrichmentUseCase(IEnrichmentUseCase):
    """Concrete enrichment usecase.

    Delegates to enrich_batch() which orchestrates EnricherService.
    Accepts an optional ontology_registry so enrichers can use
    ontology-driven entity/aspect/issue/topic matching.
    """

    def __init__(
        self,
        config: EnricherConfig,
        ontology_registry: "FileOntologyRegistry | None" = None,
    ) -> None:
        self._config = config
        self._ontology_registry = ontology_registry

    def enrich(self, inp: EnrichmentInput) -> EnrichmentOutput:
        return enrich_batch(inp, self._config, self._ontology_registry)
