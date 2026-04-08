# Phase 0 - Bootstrap and Contract Freeze

## Objective

Chot baseline ky thuat truoc khi port core de tranh drift contracts va enums.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/runtime/usecase/contract_catalog.py` | `load_contract_baseline()` | `NEW` | Nap contract snapshots tu docs, de lock schema theo release |
| `internal/runtime/usecase/enum_registry.py` | `build_enum_registry()` | `NEW` | Tong hop sentiment/severity/platform enums |
| `internal/runtime/usecase/enum_registry.py` | `normalize_enum_value(name, value)` | `NEW` | Chuan hoa uppercase/lowercase truoc khi evaluate rules |
| `internal/runtime/usecase/input_inspector.py` | `inspect_input_path(path)` | `smap/run_manifest.py::inspect_input_path` (L96) | Reuse logic inspect jsonl/zip/dir |
| `internal/runtime/usecase/run_id.py` | `default_run_id()` | `smap/run_manifest.py::default_run_id` (L344) | Tao run id format thong nhat |

## Deliverables

- Contract baseline snapshots.
- Enum dictionary da freeze.
- Run id convention lock.

## Exit criteria

- Contract mismatch tests pass.
- Enum normalization tests pass.
