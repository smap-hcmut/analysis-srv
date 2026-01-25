# Change: Fix Collector Message Format to Match Contract

## Why

Analytics service đang gửi message với **nested structure** (`success` + `payload`) nhưng Collector expect **flat structure** theo contract spec (`document/collector-crawler-contract.md` Section 3). Điều này khiến Collector không parse được message, dẫn đến analyze progress không được track.

Gap analysis chi tiết: `document/analytics-collector-gap-analysis.md`

## What Changes

- **BREAKING**: Thay đổi message format từ nested sang flat structure
- Remove wrapper `AnalyzeResultMessage` class (hoặc deprecate)
- Update `AnalyzeResultPayload.to_dict()` để return flat JSON
- Change `project_id` từ `Optional[str]` sang `str` (required)
- Remove `results` và `errors` arrays từ published message (keep internal nếu cần logging)
- Update `RabbitMQPublisher.publish_analyze_result()` để serialize flat payload

### Before (Current - Wrong)

```json
{
  "success": true,
  "payload": {
    "project_id": "proj123",
    "job_id": "proj123-brand-0",
    "task_type": "analyze_result",
    "batch_size": 50,
    "success_count": 48,
    "error_count": 2,
    "results": [...],
    "errors": [...]
  }
}
```

### After (Fixed - Correct)

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0",
  "task_type": "analyze_result",
  "batch_size": 50,
  "success_count": 48,
  "error_count": 2
}
```

## Impact

- Affected specs: `result_publishing`
- Affected code:
  - `models/messages.py` - Message dataclasses
  - `internal/consumers/main.py` - `_publish_batch_result()`, `_publish_error_result()`
  - `infrastructure/messaging/publisher.py` - `publish_analyze_result()`
  - `tests/test_models/test_messages.py`
  - `tests/test_messaging/test_publisher.py`
- Downstream: Collector service sẽ nhận đúng format và track analyze progress
