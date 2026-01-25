# Design: Fix Invalid project_id UUID Validation

## Context

Analytics service nhận events từ Crawler service qua RabbitMQ. Event payload chứa `project_id` được extract từ `job_id`. Do bug trong Crawler service, một số `project_id` có format không hợp lệ (ví dụ: `uuid-competitor` thay vì `uuid`).

**Stakeholders:**

- Analytics Service (this repo)
- Crawler Service (upstream, separate repo)

**Constraints:**

- Không thể fix Crawler service ngay lập tức (separate deployment)
- Cần backward compatible với data cũ
- Không được làm mất dữ liệu analytics

## Goals / Non-Goals

**Goals:**

- Ngăn lỗi `InvalidTextRepresentation` khi save vào PostgreSQL
- Tự động extract UUID hợp lệ từ invalid `project_id`
- Log warning để tracking và debugging
- Backward compatible với cả valid và invalid data

**Non-Goals:**

- Fix Crawler service (out of scope, separate repo)
- Migrate/fix existing data trong database
- Change database schema

## Decisions

### Decision 1: Defensive Sanitization at Repository Layer

**What:** Thêm sanitization logic trong `AnalyticsRepository.save()` để extract UUID hợp lệ từ `project_id` trước khi save.

**Why:**

- Single point of defense - tất cả data đều đi qua repository
- Không cần modify consumer logic
- Dễ test và maintain

**Alternatives considered:**

1. Fix at Consumer layer - Rejected: Phải modify nhiều chỗ
2. Fix at Orchestrator layer - Rejected: Không phải responsibility của orchestrator
3. Database trigger - Rejected: Phức tạp, khó debug

### Decision 2: Regex-based UUID Extraction

**What:** Dùng regex pattern `([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})` để extract UUID.

**Why:**

- Simple và reliable
- Không cần external library
- Handles all edge cases (UUID ở đầu, giữa, hoặc cuối string)

### Decision 3: Warning Log Instead of Error

**What:** Log warning khi sanitize invalid `project_id`, không raise error.

**Why:**

- Không làm fail batch processing
- Vẫn tracking được để fix upstream
- Data vẫn được save với correct UUID

## Risks / Trade-offs

| Risk                        | Mitigation                                       |
| --------------------------- | ------------------------------------------------ |
| Regex có thể match sai UUID | Pattern đủ specific, chỉ match valid UUID format |
| Performance overhead        | Regex compile once, match O(n) - negligible      |
| Silent data corruption      | Warning log + monitoring để detect               |

## Migration Plan

1. **Phase 1 (Hotfix):** Deploy UUID utilities + repository sanitization
2. **Phase 2 (Upstream):** Coordinate với Crawler team để fix root cause
3. **Phase 3 (Cleanup):** Remove sanitization sau khi Crawler fix deployed (optional)

**Rollback:** Revert commit, redeploy previous version

## Open Questions

- [ ] Có cần thêm Pydantic schema validation không? (Optional, có thể làm sau)
- [ ] Có cần alert/metric khi sanitize invalid project_id không?
