# Tasks: Fix Collector Message Format

## 1. Update Message Models

- [x] 1.1 Update `AnalyzeResultPayload` in `models/messages.py`

  - Change `project_id: Optional[str]` → `project_id: str`
  - Rename `results` → `_results` (internal-only)
  - Rename `errors` → `_errors` (internal-only)
  - Update `to_dict()` to return flat structure (exclude `_results`, `_errors`)
  - Add `to_json()` and `to_bytes()` methods directly on payload

- [x] 1.2 Deprecate `AnalyzeResultMessage` wrapper class

  - Add deprecation warning in docstring
  - Keep class for backward compatibility but mark as deprecated
  - Update `from_dict()` to handle both formats

- [x] 1.3 Update factory functions
  - Update `create_success_result()` to return `AnalyzeResultPayload` directly
  - Update `create_error_result()` to return `AnalyzeResultPayload` directly

## 2. Update Publisher

- [x] 2.1 Update `RabbitMQPublisher.publish_analyze_result()` in `infrastructure/messaging/publisher.py`
  - Accept `AnalyzeResultPayload` instead of `AnalyzeResultMessage`
  - Add validation: raise error if `project_id` is empty
  - Update serialization to use `payload.to_bytes()`
  - Update logging to reflect flat structure

## 3. Update Consumer

- [x] 3.1 Update `_publish_batch_result()` in `internal/consumers/main.py`

  - Build `AnalyzeResultPayload` directly (no wrapper)
  - Add validation: skip publish if `project_id` is None/empty
  - Log warning when skipping due to missing project_id

- [x] 3.2 Update `_publish_error_result()` in `internal/consumers/main.py`
  - Use `AnalyzeResultPayload` directly
  - Add same project_id validation

## 4. Update Tests

- [x] 4.1 Update `tests/test_models/test_messages.py`

  - Update `TestAnalyzeResultPayload` tests for new structure
  - Add test for flat `to_dict()` output
  - Add test for `project_id` required validation
  - Update factory function tests

- [x] 4.2 Update `tests/test_messaging/test_publisher.py`
  - Update `TestRabbitMQPublisherPublishAnalyzeResult` tests
  - Add test for empty `project_id` rejection
  - Verify published message is flat JSON

## 5. Validation

- [x] 5.1 Run all tests

  ```bash
  pytest tests/test_models/test_messages.py -v  # 23 passed
  pytest tests/test_messaging/test_publisher.py -v  # 17 passed
  ```

- [ ] 5.2 Manual verification (optional)
  - Start consumer (publishing enabled by default)
  - Send test event through RabbitMQ
  - Verify published message format matches contract spec in Collector logs
