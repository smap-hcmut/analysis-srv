"""Domain registry types — self-contained domain ontology model.

Each domain has:
  - ontology_path : path to a single self-contained YAML (OntologyRegistry format)
  - overlay_paths : optional overlay YAML files applied on top
  - contract      : domain_overlay slug for downstream consumers

DomainRegistry is built once at startup by DomainLoader and is then immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from internal.ontology.usecase.file_registry import FileOntologyRegistry


@dataclass
class DomainRuntimeConfig:
    """Full runtime configuration for one domain.

    Each domain points to a self-contained ontology YAML that includes
    entities, taxonomy, aspects, issues, intents, topics, etc.
    """

    domain_code: str
    display_name: str = ""
    contract_domain_overlay: str = ""

    # Path to the self-contained domain ontology YAML
    ontology_path: str = "config/ontology/vinfast_vn.yaml"

    # Optional overlay YAML files applied on top of the base ontology
    overlay_paths: list[str] = field(default_factory=list)

    # Runtime hints (used by NLP pipeline for quick matching)
    brand_names: list[str] = field(default_factory=list)
    topic_seeds: list[str] = field(default_factory=list)
    stop_entities: list[str] = field(default_factory=list)

    def to_runtime_ontology(self):
        """Build a pipeline OntologyConfig from this domain's runtime overlay."""
        from internal.runtime.type import OntologyConfig

        return OntologyConfig(
            domain_overlay=self.contract_domain_overlay,
            brand_names=list(self.brand_names),
            topic_seeds=list(self.topic_seeds),
            stop_entities=list(self.stop_entities),
        )

    def load_ontology_registry(self) -> "FileOntologyRegistry":
        """Load and return the FileOntologyRegistry for this domain."""
        from internal.ontology.usecase.file_registry import FileOntologyRegistry

        if self.overlay_paths:
            return FileOntologyRegistry.from_yaml_with_overlays(
                self.ontology_path,
                overlay_paths=self.overlay_paths,
            )
        return FileOntologyRegistry.from_yaml(self.ontology_path)


@dataclass
class DomainRegistry:
    """Immutable registry of domain configs, keyed by domain_code.

    Built once at startup via DomainLoader.load_from_dir().
    Thread-safe for concurrent reads (no mutation after construction).
    """

    _domains: dict[str, DomainRuntimeConfig] = field(default_factory=dict)
    _fallback_code: str = "_default"

    def register(self, cfg: DomainRuntimeConfig) -> None:
        """Register a domain config (called only during startup loading)."""
        self._domains[cfg.domain_code] = cfg

    def lookup(self, domain_code: str) -> DomainRuntimeConfig:
        """Return the domain config for domain_code, falling back to _default.

        Never returns None — always returns a valid DomainRuntimeConfig.
        If no match and no _default entry, returns a bare-minimum default.
        """
        return (
            self._domains.get(domain_code)
            or self._domains.get(self._fallback_code)
            or DomainRuntimeConfig(domain_code="_default")
        )

    def domain_codes(self) -> list[str]:
        return list(self._domains.keys())

    def __len__(self) -> int:
        return len(self._domains)


__all__ = ["DomainRuntimeConfig", "DomainRegistry"]
