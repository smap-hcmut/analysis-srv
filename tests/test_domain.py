"""Tests for domain registry types and loader.

Covers:
  - DomainRegistry.lookup() happy path, fallback, and bare-minimum default
  - DomainRegistry.register() / domain_codes() / __len__()
  - DomainLoader._parse() full and minimal YAML dicts
  - DomainLoader._parse() raises on missing/empty domain_code
  - DomainLoader.load_from_dir() with real temp YAML files
  - DomainLoader.load_from_dir() with missing directory (graceful degraded mode)
  - DomainLoader.load_from_dir() skips malformed files and loads the rest
  - DomainRuntimeConfig.to_runtime_ontology() produces correct OntologyConfig
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from internal.domain.loader import DomainLoader
from internal.domain.type import (
    DomainOntologyFilesConfig,
    DomainRegistry,
    DomainRuntimeConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cfg(
    domain_code: str = "test",
    display_name: str = "Test Domain",
    contract_domain_overlay: str = "domain-test",
    brand_names: list[str] | None = None,
    topic_seeds: list[str] | None = None,
    stop_entities: list[str] | None = None,
) -> DomainRuntimeConfig:
    return DomainRuntimeConfig(
        domain_code=domain_code,
        display_name=display_name,
        contract_domain_overlay=contract_domain_overlay,
        brand_names=brand_names or [],
        topic_seeds=topic_seeds or [],
        stop_entities=stop_entities or [],
    )


# ---------------------------------------------------------------------------
# DomainRegistry
# ---------------------------------------------------------------------------


class TestDomainRegistry:
    def test_empty_registry_len_zero(self):
        reg = DomainRegistry()
        assert len(reg) == 0

    def test_register_increments_len(self):
        reg = DomainRegistry()
        reg.register(make_cfg("a"))
        reg.register(make_cfg("b"))
        assert len(reg) == 2

    def test_lookup_known_domain(self):
        reg = DomainRegistry()
        reg.register(make_cfg("vinfast", contract_domain_overlay="domain-vinfast-vn"))
        result = reg.lookup("vinfast")
        assert result.domain_code == "vinfast"
        assert result.contract_domain_overlay == "domain-vinfast-vn"

    def test_lookup_falls_back_to_default(self):
        reg = DomainRegistry(_fallback_code="_default")
        reg.register(make_cfg("_default", contract_domain_overlay="domain-default"))
        result = reg.lookup("unknown-domain")
        assert result.domain_code == "_default"
        assert result.contract_domain_overlay == "domain-default"

    def test_lookup_empty_string_falls_back_to_default(self):
        reg = DomainRegistry(_fallback_code="_default")
        reg.register(make_cfg("_default", contract_domain_overlay="domain-default"))
        result = reg.lookup("")
        assert result.domain_code == "_default"

    def test_lookup_never_returns_none_even_without_default(self):
        """If no match and no _default entry, returns a bare-minimum DomainRuntimeConfig."""
        reg = DomainRegistry(_fallback_code="_default")
        # no entries registered at all
        result = reg.lookup("unknown")
        assert result is not None
        assert result.domain_code == "_default"

    def test_domain_codes_returns_registered_keys(self):
        reg = DomainRegistry()
        reg.register(make_cfg("a"))
        reg.register(make_cfg("b"))
        codes = reg.domain_codes()
        assert sorted(codes) == ["a", "b"]

    def test_exact_match_takes_precedence_over_fallback(self):
        reg = DomainRegistry(_fallback_code="_default")
        reg.register(make_cfg("_default", contract_domain_overlay="domain-default"))
        reg.register(make_cfg("vinfast", contract_domain_overlay="domain-vinfast-vn"))
        assert reg.lookup("vinfast").contract_domain_overlay == "domain-vinfast-vn"
        assert reg.lookup("_default").contract_domain_overlay == "domain-default"


# ---------------------------------------------------------------------------
# DomainRuntimeConfig helpers
# ---------------------------------------------------------------------------


class TestDomainRuntimeConfigHelpers:
    def test_to_runtime_ontology_domain_overlay(self):
        cfg = make_cfg(contract_domain_overlay="domain-vinfast-vn")
        ontology = cfg.to_runtime_ontology()
        assert ontology.domain_overlay == "domain-vinfast-vn"

    def test_to_runtime_ontology_brand_names_copied(self):
        cfg = make_cfg(brand_names=["VinFast", "VF8"])
        ontology = cfg.to_runtime_ontology()
        assert ontology.brand_names == ["VinFast", "VF8"]

    def test_to_runtime_ontology_mutating_result_does_not_affect_cfg(self):
        cfg = make_cfg(brand_names=["VinFast"])
        ontology = cfg.to_runtime_ontology()
        ontology.brand_names.append("INTRUDER")
        assert cfg.brand_names == ["VinFast"]

    def test_to_ontology_files_config_default_paths(self):
        cfg = make_cfg()
        files = cfg.to_ontology_files_config()
        assert files.entities_path == "config/ontology/entities.yaml"
        assert files.taxonomy_path == "config/ontology/taxonomy.yaml"
        assert files.source_channels_path == "config/ontology/source_channels.yaml"

    def test_to_ontology_files_config_custom_paths(self):
        cfg = DomainRuntimeConfig(
            domain_code="custom",
            ontology_files=DomainOntologyFilesConfig(
                entities_path="custom/ent.yaml",
                taxonomy_path="custom/tax.yaml",
                source_channels_path="custom/ch.yaml",
            ),
        )
        files = cfg.to_ontology_files_config()
        assert files.entities_path == "custom/ent.yaml"


# ---------------------------------------------------------------------------
# DomainLoader._parse()
# ---------------------------------------------------------------------------


class TestDomainLoaderParse:
    def test_full_yaml_dict_parsed_correctly(self):
        data = {
            "domain_code": "vinfast",
            "display_name": "VinFast Automotive",
            "ontology_files": {
                "entities_path": "config/ontology/entities.yaml",
                "taxonomy_path": "config/ontology/taxonomy.yaml",
                "source_channels_path": "config/ontology/source_channels.yaml",
            },
            "runtime": {
                "brand_names": ["VinFast", "VF8", "VF9"],
                "topic_seeds": ["xe điện", "ô tô điện"],
                "stop_entities": ["xe máy"],
            },
            "contract": {
                "domain_overlay": "domain-vinfast-vn",
            },
        }
        cfg = DomainLoader._parse(data)
        assert cfg.domain_code == "vinfast"
        assert cfg.display_name == "VinFast Automotive"
        assert cfg.contract_domain_overlay == "domain-vinfast-vn"
        assert cfg.brand_names == ["VinFast", "VF8", "VF9"]
        assert cfg.topic_seeds == ["xe điện", "ô tô điện"]
        assert cfg.stop_entities == ["xe máy"]

    def test_minimal_dict_only_domain_code(self):
        cfg = DomainLoader._parse({"domain_code": "minimal"})
        assert cfg.domain_code == "minimal"
        assert cfg.display_name == ""
        assert cfg.contract_domain_overlay == ""
        assert cfg.brand_names == []
        assert cfg.topic_seeds == []
        assert cfg.stop_entities == []

    def test_default_ontology_paths_when_absent(self):
        cfg = DomainLoader._parse({"domain_code": "x"})
        assert cfg.ontology_files.entities_path == "config/ontology/entities.yaml"
        assert cfg.ontology_files.taxonomy_path == "config/ontology/taxonomy.yaml"
        assert (
            cfg.ontology_files.source_channels_path
            == "config/ontology/source_channels.yaml"
        )

    def test_missing_domain_code_raises_value_error(self):
        with pytest.raises(ValueError, match="domain_code"):
            DomainLoader._parse({"display_name": "No code here"})

    def test_empty_domain_code_raises_value_error(self):
        with pytest.raises(ValueError, match="domain_code"):
            DomainLoader._parse({"domain_code": ""})

    def test_null_runtime_block_gives_empty_lists(self):
        cfg = DomainLoader._parse({"domain_code": "x", "runtime": None})
        assert cfg.brand_names == []
        assert cfg.topic_seeds == []

    def test_null_contract_block_gives_empty_overlay(self):
        cfg = DomainLoader._parse({"domain_code": "x", "contract": None})
        assert cfg.contract_domain_overlay == ""


# ---------------------------------------------------------------------------
# DomainLoader.load_from_dir() — filesystem tests
# ---------------------------------------------------------------------------


class TestDomainLoaderLoadFromDir:
    def test_loads_valid_yaml_file(self, tmp_path: Path):
        (tmp_path / "vinfast.yaml").write_text(
            textwrap.dedent("""\
                domain_code: "vinfast"
                display_name: "VinFast"
                contract:
                  domain_overlay: "domain-vinfast-vn"
                runtime:
                  brand_names: ["VinFast", "VF8"]
            """),
            encoding="utf-8",
        )
        registry = DomainLoader.load_from_dir(str(tmp_path))
        assert len(registry) == 1
        cfg = registry.lookup("vinfast")
        assert cfg.domain_code == "vinfast"
        assert cfg.contract_domain_overlay == "domain-vinfast-vn"
        assert cfg.brand_names == ["VinFast", "VF8"]

    def test_loads_multiple_yaml_files(self, tmp_path: Path):
        for code in ("alpha", "beta", "gamma"):
            (tmp_path / f"{code}.yaml").write_text(
                f'domain_code: "{code}"\ncontract:\n  domain_overlay: "domain-{code}"\n',
                encoding="utf-8",
            )
        registry = DomainLoader.load_from_dir(str(tmp_path))
        assert len(registry) == 3
        assert sorted(registry.domain_codes()) == ["alpha", "beta", "gamma"]

    def test_missing_directory_returns_empty_registry(self, tmp_path: Path):
        registry = DomainLoader.load_from_dir(str(tmp_path / "nonexistent"))
        assert len(registry) == 0

    def test_missing_directory_lookup_still_never_returns_none(self, tmp_path: Path):
        registry = DomainLoader.load_from_dir(str(tmp_path / "nonexistent"))
        result = registry.lookup("anything")
        assert result is not None

    def test_malformed_yaml_file_skipped_others_loaded(self, tmp_path: Path):
        (tmp_path / "good.yaml").write_text(
            'domain_code: "good"\ncontract:\n  domain_overlay: "domain-good"\n',
            encoding="utf-8",
        )
        (tmp_path / "bad.yaml").write_text(
            ": invalid: yaml: [unclosed",
            encoding="utf-8",
        )
        registry = DomainLoader.load_from_dir(str(tmp_path))
        # 'bad.yaml' parses as a string, not a dict — _parse will raise ValueError
        # OR yaml.safe_load fails — either way, good.yaml should still load
        assert registry.lookup("good").domain_code == "good"

    def test_yaml_without_domain_code_skipped(self, tmp_path: Path):
        (tmp_path / "nodomain.yaml").write_text(
            'display_name: "No domain_code field"\n',
            encoding="utf-8",
        )
        (tmp_path / "valid.yaml").write_text(
            'domain_code: "valid"\n',
            encoding="utf-8",
        )
        registry = DomainLoader.load_from_dir(str(tmp_path))
        assert len(registry) == 1
        assert registry.lookup("valid").domain_code == "valid"

    def test_non_yaml_files_ignored(self, tmp_path: Path):
        (tmp_path / "readme.txt").write_text("not a yaml file", encoding="utf-8")
        (tmp_path / "config.json").write_text(
            '{"domain_code": "json"}', encoding="utf-8"
        )
        (tmp_path / "valid.yaml").write_text('domain_code: "valid"\n', encoding="utf-8")
        registry = DomainLoader.load_from_dir(str(tmp_path))
        assert len(registry) == 1

    def test_custom_fallback_code_used(self, tmp_path: Path):
        (tmp_path / "_default.yaml").write_text(
            'domain_code: "_default"\ncontract:\n  domain_overlay: "domain-default"\n',
            encoding="utf-8",
        )
        registry = DomainLoader.load_from_dir(str(tmp_path), fallback_code="_default")
        result = registry.lookup("does-not-exist")
        assert result.domain_code == "_default"
        assert result.contract_domain_overlay == "domain-default"

    def test_real_config_domains_dir_loads(self):
        """Smoke test: the actual config/domains/ directory must load without error."""
        registry = DomainLoader.load_from_dir(
            "config/domains", fallback_code="_default"
        )
        assert len(registry) >= 1
        # _default must always be present
        default = registry.lookup("_default")
        assert default.contract_domain_overlay != ""

    def test_real_vinfast_domain_loads(self):
        """Smoke test: vinfast.yaml must load and have expected overlay slug."""
        registry = DomainLoader.load_from_dir(
            "config/domains", fallback_code="_default"
        )
        vinfast = registry.lookup("vinfast")
        assert vinfast.domain_code == "vinfast"
        assert vinfast.contract_domain_overlay == "domain-vinfast-vn"

    def test_default_overlay_is_not_empty(self):
        """Critical: _default domain_overlay must NOT be empty (knowledge-srv hard gate)."""
        registry = DomainLoader.load_from_dir(
            "config/domains", fallback_code="_default"
        )
        default = registry.lookup("_default")
        assert default.contract_domain_overlay != "", (
            "_default domain_overlay is empty — knowledge-srv will silently drop all digest messages"
        )
