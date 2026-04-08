# Phase 0 - Readiness

## Muc tieu

Chot pham vi migration, freeze contract baseline, va thong nhat cach do quality truoc khi code.

## Cong viec chinh

1. Chot scope in/out theo migration plan.
2. Freeze contract reference:
   - knowledge contracts (batch, insights, digest)
   - crisis event contract cho project
3. Chot enum dictionary dung chung:
   - sentiment labels
   - severity labels
   - topic/issue keys
4. Chot data lineage tu ingest -> analysis -> knowledge/project.
5. Chot benchmark baseline cua service hien tai (latency, error rate, throughput).

## Deliverables

- Scope sign-off doc.
- Contract baseline snapshot.
- Enum mapping sheet.
- Baseline metrics report.

## Test/validation

- Validate parser voi sample payloads da freeze.
- Validate contract schemas bang json schema/unit tests.

## Exit criteria

- Scope va contracts khong con ambiguous.
- Baseline metric da co de so sanh sau migration.
