# Risks, Testing, and Cutover

## 1) Top Risks

1. Schema mismatch giữa input UAP và parser mới.
2. Contract drift với knowledge/project khi đổi core.
3. Inconsistent enums (sentiment, severity, platform).
4. Hiệu năng giảm khi batch lớn do enrichment nặng.
5. Duplicate publish nếu thiếu idempotency/outbox.

## 2) Testing Strategy

### Unit tests

- Rule tests cho dedup/spam/crisis.
- Mapper tests cho contract payload builders.
- Domain service tests cho entity/semantic/topic.

### Integration tests

- ingest -> analysis inbound.
- analysis -> knowledge topics.
- analysis -> project crisis topic.
- DB write/read consistency tests.

### Regression tests

- Golden dataset so sánh output trước/sau migrate.
- Threshold tests cho WARNING/CRITICAL.

## 3) Cutover Strategy

### Step A: Shadow mode

- Chạy pipeline mới song song pipeline cũ.
- Không publish production topics, chỉ so sánh output.

### Step B: Partial traffic

- Bật publish thật cho 1-2 projects pilot.
- Theo dõi lag, error rate, alert quality.

### Step C: Full cutover

- Chuyển toàn bộ projects.
- Giữ rollback switch trong 1-2 tuần đầu.

## 4) Rollback Plan

- Toggle config để route lại sang pipeline cũ.
- Tắt producer của pipeline mới.
- Giữ raw events để replay sau rollback.

## 5) Definition of Done

- E2E pass trên staging và pilot production.
- Contract compatibility 100% với downstream bắt buộc.
- Crisis alert chính xác theo config project.
- Có runbook, dashboard, và oncall checklist.
