"""DomainLoader — loads domain YAML configs from a directory into a DomainRegistry.

Expected YAML structure per file (e.g. config/domains/vinfast.yaml):

    domain_code: "vinfast"
    display_name: "VinFast Automotive"

    ontology_files:
      entities_path: "config/ontology/entities.yaml"
      taxonomy_path: "config/ontology/taxonomy.yaml"
      source_channels_path: "config/ontology/source_channels.yaml"

    runtime:
      brand_names:
        - "VinFast"
        - "VF8"
      topic_seeds:
        - "xe điện"
      stop_entities: []

    contract:
      domain_overlay: "domain-vinfast-vn"

Files are loaded in sorted order (alphabetical). If the directory does not exist
or a file is malformed, a warning is emitted and the service continues in
degraded mode (missing domain → falls back to _default).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .type import DomainOntologyFilesConfig, DomainRegistry, DomainRuntimeConfig

logger = logging.getLogger(__name__)

_DEFAULT_ENTITIES_PATH = "config/ontology/entities.yaml"
_DEFAULT_TAXONOMY_PATH = "config/ontology/taxonomy.yaml"
_DEFAULT_CHANNELS_PATH = "config/ontology/source_channels.yaml"


class DomainLoader:
    """Factory that scans a directory and returns a populated DomainRegistry."""

    @staticmethod
    def load_from_dir(
        domains_dir: str,
        fallback_code: str = "_default",
    ) -> DomainRegistry:
        """Load all *.yaml files in domains_dir into a DomainRegistry.

        Args:
            domains_dir:   Path to the directory containing per-domain YAML files.
            fallback_code: domain_code to use when a record's domain_type_code
                           has no matching entry. Defaults to "_default".

        Returns:
            Populated DomainRegistry. Returns an empty registry (with just the
            hard-coded _default fallback) if the directory does not exist.
        """
        registry = DomainRegistry(_fallback_code=fallback_code)
        path = Path(domains_dir)

        if not path.exists():
            logger.warning(
                "internal.domain.loader: domains_dir=%r does not exist, "
                "domain registry will use hard-coded fallback only",
                domains_dir,
            )
            return registry

        loaded = 0
        for yaml_file in sorted(path.glob("*.yaml")):
            try:
                with yaml_file.open(encoding="utf-8") as f:
                    data: dict[str, Any] = yaml.safe_load(f) or {}

                cfg = DomainLoader._parse(data, source=str(yaml_file))
                registry.register(cfg)
                loaded += 1
                logger.debug(
                    "internal.domain.loader: loaded domain=%r from %s",
                    cfg.domain_code,
                    yaml_file.name,
                )
            except Exception as exc:
                logger.warning(
                    "internal.domain.loader: skipping malformed domain file %s: %s",
                    yaml_file,
                    exc,
                )

        logger.info(
            "internal.domain.loader: loaded %d domain(s) from %r: %s",
            loaded,
            domains_dir,
            registry.domain_codes(),
        )
        return registry

    @staticmethod
    def _parse(data: dict[str, Any], source: str = "") -> DomainRuntimeConfig:
        """Parse a raw YAML dict into a DomainRuntimeConfig.

        Raises:
            KeyError: if 'domain_code' is missing.
            ValueError: if 'domain_code' is empty.
        """
        domain_code = data.get("domain_code", "")
        if not domain_code:
            raise ValueError(f"domain_code is required (source={source!r})")

        ontology_raw = data.get("ontology_files", {}) or {}
        runtime_raw = data.get("runtime", {}) or {}
        contract_raw = data.get("contract", {}) or {}

        ontology_files = DomainOntologyFilesConfig(
            entities_path=ontology_raw.get("entities_path", _DEFAULT_ENTITIES_PATH),
            taxonomy_path=ontology_raw.get("taxonomy_path", _DEFAULT_TAXONOMY_PATH),
            source_channels_path=ontology_raw.get(
                "source_channels_path", _DEFAULT_CHANNELS_PATH
            ),
        )

        return DomainRuntimeConfig(
            domain_code=domain_code,
            display_name=data.get("display_name", ""),
            contract_domain_overlay=contract_raw.get("domain_overlay", ""),
            ontology_files=ontology_files,
            brand_names=list(runtime_raw.get("brand_names", []) or []),
            topic_seeds=list(runtime_raw.get("topic_seeds", []) or []),
            stop_entities=list(runtime_raw.get("stop_entities", []) or []),
        )


__all__ = ["DomainLoader"]
