"""new — factory function for EnrichmentUseCase.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from internal.enrichment.interface import IEnrichmentUseCase
from internal.enrichment.type import EnricherConfig
from internal.enrichment.usecase.usecase import EnrichmentUseCase


def new_enrichment_usecase(
    config: EnricherConfig | None = None,
) -> IEnrichmentUseCase:
    """Create and return a configured EnrichmentUseCase.

    Args:
        config: EnricherConfig, or None to use defaults (all stages enabled).

    Returns:
        IEnrichmentUseCase
    """
    if config is None:
        config = EnricherConfig()
    return EnrichmentUseCase(config)
