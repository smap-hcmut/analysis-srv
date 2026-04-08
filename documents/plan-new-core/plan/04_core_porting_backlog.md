# Core Porting Backlog

Mục tiêu: backlog cụ thể để đem core từ smap-analyse vào analysis-srv theo thứ tự an toàn.

## Wave 1 - Foundation and Contracts

1. Chuẩn hóa UAP schema adapter (analysis inbound DTO).
2. Tạo run context + trace context chuẩn.
3. Implement outbound contract builders cho knowledge topics.
4. Implement outbox publisher với ordering theo run.

Deliverable:

- Input parse/validate pass.
- Publish test payload đúng schema.

## Wave 2 - Processing Core

1. Port normalization pipeline.
2. Port dedup service.
3. Port spam scoring service.
4. Port thread builder.

Deliverable:

- Tạo được mentions/thread artifacts ổn định.

## Wave 3 - Enrichment Core

1. Port entity extraction + canonicalization engine.
2. Port semantic inference (sentiment/issue/aspect/target).
3. Port topic candidate enrichment + artifacts.

Deliverable:

- Sinh full enrichment facts với confidence.

## Wave 4 - Analytics and Insights

1. Port marts builder.
2. Port metrics computation.
3. Port BI reports builder.
4. Port insight generator.

Deliverable:

- Sinh metrics + bi reports + insight cards tương thích knowledge contract.

## Wave 5 - Crisis and Review

1. Port/implement review queue logic.
2. Implement crisis evaluator theo project config.
3. Publish `project.crisis.detected`.

Deliverable:

- Alert WARNING/CRITICAL hoạt động theo rule config.

## Wave 6 - Hardening

1. Performance profiling (batch lớn).
2. Replay tool theo run_id.
3. Integration tests liên service.
4. Runbook và operational dashboards.

Deliverable:

- Ready for staged rollout.

## Backlog metadata template

Dùng mẫu này cho từng task:

- Task ID:
- Module:
- Source reference (smap-analyse path):
- Target module (analysis-srv path):
- Dependencies:
- Acceptance criteria:
- Test cases:
