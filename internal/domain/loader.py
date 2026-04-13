"""DomainLoader — loads domain YAML configs from a directory into a DomainRegistry.

Expected YAML structure per file (e.g. config/domains/vinfast.yaml):

    domain_code: "vinfast"
    display_name: "VinFast Automotive"

    ontology:
      path: "config/ontology/vinfast_vn.yaml"
      overlays: []

    runtime:
      brand_names:
        - "VinFast"
        - "VF8"
      topic_seeds:
        - "xe điện"
      stop_entities: []

    contract:
      domain_overlay: "domain-vinfast-vn"
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .type import DomainRegistry, DomainRuntimeConfig

logger = logging.getLogger(__name__)

_DEFAULT_ONTOLOGY_PATH = "config/ontology/vinfast_vn.yaml"


class DomainLoader:
    """Factory that scans a directory and returns a populated DomainRegistry."""

    @staticmethod
    def load_from_dir(
        domains_dir: str,
        fallback_code: str = "_default",
    ) -> DomainRegistry:
        """Load all *.yaml files in domains_dir into a DomainRegistry."""
        registry = DomainRegistry(_fallback_code=fallback_code)
        path = Path(domains_dir)

        if not path.exists():
            logger.warning(
                "DomainLoader: domains_dir=%r does not exist, "
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
                    "DomainLoader: loaded domain=%r from %s",
                    cfg.domain_code,
                    yaml_file.name,
                )
            except Exception as exc:
                logger.warning(
                    "DomainLoader: skipping malformed domain file %s: %s",
                    yaml_file,
                    exc,
                )

        logger.info(
            "DomainLoader: loaded %d domain(s) from %r: %s",
            loaded,
            domains_dir,
            registry.domain_codes(),
        )
        return registry

    @staticmethod
    def _parse(data: dict[str, Any], source: str = "") -> DomainRuntimeConfig:
        """Parse a raw YAML dict into a DomainRuntimeConfig."""
        domain_code = data.get("domain_code", "")
        if not domain_code:
            raise ValueError(f"domain_code is required (source={source!r})")

        # New format: ontology.path (self-contained)
        ontology_raw = data.get("ontology", {}) or {}
        runtime_raw = data.get("runtime", {}) or {}
        contract_raw = data.get("contract", {}) or {}

        ontology_path = ontology_raw.get("path", _DEFAULT_ONTOLOGY_PATH)
        overlay_paths = list(ontology_raw.get("overlays", []) or [])

        return DomainRuntimeConfig(
            domain_code=domain_code,
            display_name=data.get("display_name", ""),
            contract_domain_overlay=contract_raw.get("domain_overlay", ""),
            ontology_path=ontology_path,
            overlay_paths=overlay_paths,
            brand_names=list(runtime_raw.get("brand_names", []) or []),
            topic_seeds=list(runtime_raw.get("topic_seeds", []) or []),
            stop_entities=list(runtime_raw.get("stop_entities", []) or []),
        )


__all__ = ["DomainLoader"]
