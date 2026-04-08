# Phase 2 - Ingestion and Validation

## Objective

Port full ingestion/validation path va schema parsing cho UAP input.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/ingestion/usecase/ingest_batch.py` | `ingest_batch(input_path, materialized_raw_jsonl_path=None)` | `smap/ingestion/service.py::ingest_batch` (L36) | Parse + profile + validation report |
| `internal/ingestion/usecase/ingest_batch.py` | `_present_count(field_stats, *field_names)` | `smap/ingestion/service.py::_present_count` (L32) | Helper profile notes |
| `internal/validation/usecase/validate_batch.py` | `validate_batch(path_or_bundle)` | `smap/validation/service.py::validate_batch` (L34) | Structural validation |
| `internal/validation/usecase/profile_batch.py` | `profile_batch(path_or_bundle)` | `smap/validation/service.py::profile_batch` (L59) | Batch profiling |
| `internal/ingestion/usecase/readers.py` | `is_valid_jsonl_archive_member(name)` | `smap/ingestion/readers.py::is_valid_jsonl_archive_member` (L20) | Bo qua __MACOSX va AppleDouble |
| `internal/ingestion/usecase/readers.py` | `iter_jsonl_archive_members(archive)` | `smap/ingestion/readers.py::iter_jsonl_archive_members` (L32) | Filter archive members |
| `internal/ingestion/usecase/readers.py` | `iter_jsonl_file(path)` | `smap/ingestion/readers.py::iter_jsonl_file` (L47) | Read jsonl file |
| `internal/ingestion/usecase/readers.py` | `iter_zip_jsonl(path)` | `smap/ingestion/readers.py::iter_zip_jsonl` (L60) | Read zip jsonl |
| `internal/ingestion/usecase/readers.py` | `iter_batch_source(path)` | `smap/ingestion/readers.py::iter_batch_source` (L80) | Unified iterator |
| `internal/model/uap_parser.py` | `parse_uap_record(payload)` | `smap/contracts/uap.py::parse_uap_record` (L353) | Canonical UAP parser |
| `internal/model/uap_parser.py` | `content_title(record)` | `smap/contracts/uap.py::content_title` (L368) | Canonical title accessor |
| `internal/model/uap_parser.py` | `content_keywords(record)` | `smap/contracts/uap.py::content_keywords` (L372) | Canonical keywords accessor |
| `internal/model/uap_parser.py` | `content_links(record)` | `smap/contracts/uap.py::content_links` (L376) | Canonical links accessor |
| `internal/model/uap_parser.py` | `engagement_saves(record)` | `smap/contracts/uap.py::engagement_saves` (L380) | save/bookmark alias |

## Deliverables

- Ingestion path cho jsonl/zip/kafka.
- Validation va profiling reports.

## Exit criteria

- Parser tests pass tren payload variants.
- Batch validation output on dinh.
