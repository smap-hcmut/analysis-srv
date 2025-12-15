# Change: Fix Invalid project_id UUID Validation

## Why

Production analytics pipeline đang gặp lỗi `InvalidTextRepresentation` khi lưu dữ liệu vào PostgreSQL. Nguyên nhân: upstream Crawler service gửi `project_id` với format không hợp lệ (`fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor` thay vì UUID chuẩn).

**Root Cause:** Crawler service dùng `rsplit("-", 2)` để extract `project_id` từ `job_id`, nhưng logic này fail khi `job_id` có format `{uuid}-competitor-{name}-{index}`.

**Impact:**

- Thời gian: 2025-12-15 13:33:46
- Platform: TIKTOK
- Tỷ lệ: Một số item trong mỗi batch bị fail, gây mất dữ liệu analytics

## What Changes

1. **Thêm UUID utility module** (`utils/uuid_utils.py`)

   - `extract_uuid()`: Extract UUID hợp lệ từ string
   - `is_valid_uuid()`: Validate UUID format

2. **Thêm defensive sanitization trong Repository layer**

   - Sanitize `project_id` trước khi save vào database
   - Log warning khi phải sanitize invalid value

3. **Thêm Pydantic schema validation cho event payload** (optional)
   - Auto-sanitize `project_id` khi parse event
   - Backward compatible với data cũ từ Crawler

## Impact

- Affected specs: `event_consumption`, `crawler_metadata`
- Affected code:
  - `utils/uuid_utils.py` (tạo mới)
  - `repository/analytics_repository.py`
  - `internal/schemas/event_schema.py` (tạo mới - optional)

## References

- Production Issue Report: `document/PRODUCTION_ISSUE_2025-12-15.md`
- Crawler Event Fields Analysis: `document/analytics-event-fields-analysis.md`
