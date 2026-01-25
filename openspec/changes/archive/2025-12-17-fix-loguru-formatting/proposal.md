# Change: Fix Loguru Logger Formatting Issues

## Why

Production logs đang hiển thị `%s`, `%d`, `%.1f%%` thay vì giá trị thực tế. Nguyên nhân là code đang sử dụng printf-style formatting với Loguru, nhưng Loguru không tự động format như `logging` module chuẩn của Python.

Ví dụ từ production log:

```
logger.info("Starting analytics pipeline for post_id=%s", post_id)
# Output: Starting analytics pipeline for post_id=%s
# Expected: Starting analytics pipeline for post_id=abc123
```

## What Changes

- **Fix all logger calls** từ printf-style (`%s`, `%d`) sang f-string hoặc Loguru's `{}` format
- **Update core/logger.py** với documentation rõ ràng về cách sử dụng đúng
- **Create logging guide document** để team có thể áp dụng cho các service khác

## Impact

- Affected specs: `monitoring`
- Affected code:
  - `core/logger.py` - Logger configuration
  - `infrastructure/messaging/publisher.py` - 2 logger calls
  - `infrastructure/storage/minio_client.py` - 4 logger calls
  - `services/analytics/orchestrator.py` - 4 logger calls
  - `internal/consumers/main.py` - 15+ logger calls
  - `internal/consumers/item_processor.py` - 2 logger calls
  - `repository/analytics_repository.py` - 5 logger calls
  - `repository/crawl_error_repository.py` - 3 logger calls
  - `utils/debug_logging.py` - 8 logger calls
  - `core/config_validation.py` - 5 logger calls
  - `command/consumer/main.py` - 1 logger call

## Files to Create

- `document/logging-guide.md` - Comprehensive logging guide for reuse across services
