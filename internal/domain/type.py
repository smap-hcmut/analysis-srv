"""Domain registry types.

A "domain" in this context maps to a business vertical tracked by a project,
e.g. "vinfast" (automotive), "facial_cleanser" (FMCG), etc.

Each domain has:
  - ontology_files  : paths to YAML ontology data (entities, taxonomy, channels)
  - runtime overlay : brand_names, topic_seeds, stop_entities used during NLP
  - contract        : domain_overlay slug written into Layer-1 Kafka messages

DomainRegistry is built once at startup by DomainLoader and is then immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class DomainOntologyFilesConfig:
    """Paths to YAML ontology files for this domain."""

    entities_path: str = "config/ontology/entities.yaml"
    taxonomy_path: str = "config/ontology/taxonomy.yaml"
    source_channels_path: str = "config/ontology/source_channels.yaml"


@dataclass
class DomainRuntimeConfig:
    """Full runtime configuration for one domain.

    Holds everything the pipeline needs to handle a record tagged with
    a specific domain_type_code.
    """

    domain_code: str
    display_name: str = ""
    contract_domain_overlay: str = ""
    ontology_files: DomainOntologyFilesConfig = field(
        default_factory=DomainOntologyFilesConfig
    )
    brand_names: list[str] = field(default_factory=list)
    topic_seeds: list[str] = field(default_factory=list)
    stop_entities: list[str] = field(default_factory=list)

    def to_runtime_ontology(self):  # -> internal.runtime.type.OntologyConfig
        """Build a pipeline OntologyConfig from this domain's runtime overlay."""
        from internal.runtime.type import OntologyConfig

        return OntologyConfig(
            domain_overlay=self.contract_domain_overlay,
            brand_names=list(self.brand_names),
            topic_seeds=list(self.topic_seeds),
            stop_entities=list(self.stop_entities),
        )

    def to_ontology_files_config(self):  # -> config.config.OntologyConfig
        """Build a config-layer OntologyConfig (file paths) for FileOntologyRegistry."""
        from config.config import OntologyConfig as FilesConfig

        return FilesConfig(
            entities_path=self.ontology_files.entities_path,
            taxonomy_path=self.ontology_files.taxonomy_path,
            source_channels_path=self.ontology_files.source_channels_path,
        )


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


__all__ = ["DomainOntologyFilesConfig", "DomainRuntimeConfig", "DomainRegistry"]
