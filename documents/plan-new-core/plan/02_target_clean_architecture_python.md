# Target Clean Architecture (Python) - Corrected for analysis-srv

## Why this version

Version truoc sai vi dung kieu layer tong quat (`domain/application/infrastructure`) khong khop convention hien tai cua repo analysis-srv.

Kien truc dung cho repo nay phai la:

- Module theo chieu doc (vertical module)
- Moi module co `interface.py`, `type.py`, `constant.py`, `errors.py`, `usecase/`, `delivery/`, `repository/`
- Clean architecture duoc enforce bang dependency rule trong tung module, khong bat buoc gom tat ca vao 3 thu muc lon.

## Dependency rule (ap dung theo module)

1. `delivery/*` chi duoc goi `usecase` interface, khong chua business logic.
2. `usecase/*` chi phu thuoc vao interface/repository ports, khong import framework transport.
3. `repository/*` xu ly persistence, khong chua policy nghiep vu.
4. `pkg/*` la adapter ky thuat dung chung (kafka, postgre, logger, minio, redis).

## De xuat cau truc dung (module-based clean architecture)

```text
analysis-srv/
  apps/
    consumer/
      main.py

  internal/
    model/
      # system-level DTOs cho wire contracts (UAP, InsightMessage, ...)

    pipeline/
      __init__.py
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        run_pipeline.py
        helpers.py

    ingestion/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        ingest_batch.py
        validate_batch.py
      delivery/
        kafka/
          consumer/
            new.py
            handler.py
            workers.py
            presenters.py

    normalization/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        normalize_mentions.py
        helpers.py

    dedup/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        annotate.py

    spam/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        annotate.py

    enrichment/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        enrich_entities.py
        enrich_semantic.py
        enrich_topics.py
        helpers.py
      repository/
        interface.py
        option.py
        errors.py
        new.py
        postgre/
          new.py
          feedback_store.py

    review/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        queue_items.py
        seed_ontology_version.py
      repository/
        interface.py
        option.py
        errors.py
        new.py
        postgre/
          new.py
          review_item.py
          review_item_query.py

    reporting/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        build_marts.py
        build_metrics.py
        build_bi_reports.py
        build_insights.py

    contract_publisher/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        publish_knowledge_batch.py
        publish_knowledge_insights.py
        publish_knowledge_digest.py
        publish_project_crisis.py
      delivery/
        kafka/
          producer/
            new.py
            producer.py
            presenters.py

    crisis/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        evaluate_rules.py
        resolve_severity.py
      repository/
        interface.py
        option.py
        errors.py
        new.py
        postgre/
          new.py
          alert.py
          alert_query.py

    storage/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        write_parquet.py
        write_manifest.py

    runtime/
      interface.py
      type.py
      constant.py
      errors.py
      usecase/
        new.py
        resolve_ontology.py
        doctor.py

    consumer/
      # orchestrator wiring cho domains (giu nhu convention hien tai)
      interface.py
      type.py
      registry.py
      server.py

  pkg/
    kafka/
    postgre/
    logger/
    minio/
    redis/
    phobert_onnx/
    spacy_yake/
```

## Mapping from smap-analyse -> analysis-srv modules

- `smap/pipeline.py` -> `internal/pipeline/usecase/run_pipeline.py`
- `smap/ingestion/*` -> `internal/ingestion/*`
- `smap/normalization/*` -> `internal/normalization/*`
- `smap/dedup/*` -> `internal/dedup/*`
- `smap/quality/spam.py` -> `internal/spam/*`
- `smap/enrichers/*` -> `internal/enrichment/*`
- `smap/review/*` -> `internal/review/*`
- `smap/marts/*`, `smap/analytics/*`, `smap/bi/*`, `smap/insights/*` -> `internal/reporting/*`
- `run manifest + runtime doctor` -> `internal/runtime/*` + `internal/storage/*`
- output contracts cho knowledge/project -> `internal/contract_publisher/*` + `internal/crisis/*`

## Rules for method/file splitting (must follow)

1. `usecase/new.py` chi la factory.
2. Moi public method dat trong file rieng (`run_pipeline.py`, `evaluate_rules.py`, ...).
3. Private helper bo vao `helpers.py`.
4. Input/Output dataclasses chi dat trong `type.py`.
5. Repository options chi dat trong `repository/option.py`.

## Non-goals in this structure

- Khong doi convention thanh monolith folder `domain/application/infrastructure`.
- Khong dua business logic vao `delivery` hoac `pkg`.

## Minimal acceptance checks

1. Moi module moi co du bo file theo convention python hien tai.
2. Delivery layer import usecase interface, khong import repository concrete.
3. Usecase layer co unit test cho rules nghiep vu chinh.
4. Contract publisher pass schema checks voi knowledge/project payloads.
