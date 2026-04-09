"""EnrichmentUseCase — implements IEnrichmentUseCase.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from internal.enrichment.interface import IEnrichmentUseCase
from internal.enrichment.type import (
    EnricherConfig,
    EnrichmentInput,
    EnrichmentOutput,
)
from internal.enrichment.usecase.enrich_batch import enrich_batch


class EnrichmentUseCase(IEnrichmentUseCase):
    """Concrete enrichment usecase.

    Delegates to enrich_batch() which orchestrates EnricherService.
    """

    def __init__(self, config: EnricherConfig) -> None:
        self._config = config

    def enrich(self, inp: EnrichmentInput) -> EnrichmentOutput:
        return enrich_batch(inp, self._config)
