# Delivery Milestones

## Milestone M1 - Skeleton and Contracts (1-2 tuần)

- Chốt target architecture và folder structure.
- Chạy được pipeline skeleton với mock enrichers.
- Publish đủ 3 topics knowledge bằng dữ liệu mock hợp lệ.

Gate M1:

- Contract validation pass.
- CI chạy unit tests nền tảng.

## Milestone M2 - Core Processing (2-3 tuần)

- Port normalize/dedup/spam/threads.
- Persist operational tables vào PostgreSQL/Timescale.

Gate M2:

- Dữ liệu đầu ra ổn định trên sample batch.
- Không có regression so với baseline hiện tại.

## Milestone M3 - Enrichment and BI (3-4 tuần)

- Port entity/semantic/topic.
- Port marts/metrics/bi/insights.

Gate M3:

- Insight quality review đạt ngưỡng.
- Knowledge contract e2e pass trên staging.

## Milestone M4 - Crisis and Integration (2 tuần)

- Tích hợp lấy crisis config theo project.
- Đánh giá trigger và publish alert.
- Hoàn thiện trace propagation end-to-end.

Gate M4:

- Trigger WARNING/CRITICAL đúng test scenarios.
- Replay deterministic cho cùng dataset.

## Milestone M5 - Production Readiness (1-2 tuần)

- Tối ưu hiệu năng và chi phí runtime.
- Bổ sung dashboards, alerts, runbook.
- Cutover plan và rollback plan.

Gate M5:

- Soak test đạt SLA.
- Ready sign-off từ data + product + platform.
