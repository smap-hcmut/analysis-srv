# Phase 7 - Review, DB, Persistence

## Objective

Port review workflow, DB readiness checks, va storage persistence.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/review/usecase/seed_ontology_version.py` | `seed_ontology_version(session, registry)` | `smap/review/service.py::seed_ontology_version` (L10) | Ensure ontology version row |
| `internal/review/usecase/queue_items.py` | `queue_review_items(session, enrichment, settings, review_contexts, policy_engine)` | `smap/review/service.py::queue_review_items` (L83) | Queue low-confidence items |
| `internal/review/usecase/context_index.py` | `build_review_context_index(mentions, registry, source_family=None, source_domain=None)` | `smap/review/context.py::build_review_context_index` (L145) | Build review scope context |
| `internal/review/usecase/migrations.py` | `get_database_status(settings)` | `smap/review/migrations.py::get_database_status` (L58) | DB status check |
| `internal/review/usecase/migrations.py` | `require_database_ready(settings)` | `smap/review/migrations.py::require_database_ready` (L64) | Fail fast if DB not ready |
| `internal/review/usecase/migrations.py` | `upgrade_database(settings)` | `smap/review/migrations.py::upgrade_database` (L72) | Alembic upgrade |
| `internal/storage/usecase/write_text.py` | `write_text_if_changed(path, payload)` | `smap/storage/repository.py::write_text_if_changed` (L18) | Avoid unnecessary writes |
| `internal/storage/usecase/copy_file.py` | `copy_file_if_needed(source, destination)` | `smap/storage/repository.py::copy_file_if_needed` (L27) | Copy bronze raw |
| `internal/storage/usecase/write_parquet.py` | `write_models_parquet(path, records)` | `smap/storage/repository.py::write_models_parquet` (L34) | Persist model records |
| `internal/storage/usecase/write_tables.py` | `write_table_bundle(output_dir, tables)` | `smap/storage/repository.py::write_table_bundle` (L44) | Persist marts tables |
| `internal/storage/usecase/register_duckdb.py` | `register_parquet_tables(duckdb_path, table_paths)` | `smap/storage/repository.py::register_parquet_tables` (L53) | Optional BI query store |

## Deliverables

- Review queue flow hoat dong.
- DB migration/readiness commands.
- Storage persistence helpers.

## Exit criteria

- Review queue metrics on dinh.
- DB readiness checks pass in CI/staging.
