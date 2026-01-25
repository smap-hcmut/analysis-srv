# Implementation Tasks

## 1. Foundation & Utilities (2-3 days)

- [x] 1.1 Create `core/constants.py` with ErrorCode and ErrorCategory enums (17 codes)
- [x] 1.2 Create `utils/project_id_extractor.py` with extraction logic
- [x] 1.3 Write unit tests for project_id extraction (11 test cases minimum)
- [x] 1.4 Add error categorization function with tests
- [x] 1.5 Update `core/config.py` with 10+ new settings (event, batch, error, MinIO)

## 2. Database Schema (1-2 days)

- [x] 2.1 Update `models/database.py` - Add 10 fields to PostAnalytics model
- [x] 2.2 Create CrawlError model with indexes
- [x] 2.3 Create Alembic migration `add_crawler_integration_fields`
- [x] 2.4 Test migration upgrade/downgrade on development database
- [x] 2.5 Add indexes for `job_id`, `fetch_status`, `task_type`, `error_code`
- [x] 2.6 Validate schema changes with test data

## 3. Repository (1 day)

- [x] 3.1 Create `repository/crawl_error_repository.py` with save/get methods
- [x] 3.2 Update `repository/analytics_repository.py` save method for new fields
- [x] 3.3 Add `get_error_stats()` method to CrawlErrorRepository
- [x] 3.4 Write repository unit tests
- [x] 3.5 Test database operations with sample data

## 4. Event Consumption (2-3 days)

- [x] 4.1 Update `internal/consumers/main.py` - Add event schema parsing
- [x] 4.2 Implement MinIO path splitting (`crawl-results/...` → bucket + path)
- [x] 4.3 Add event metadata extraction (event_id, timestamp, payload fields)
- [x] 4.4 Implement dual-mode message detection (new vs legacy format)
- [x] 4.5 Update `infrastructure/messaging/rabbitmq.py` - Add exchange binding
- [x] 4.6 Update `command/consumer/main.py` - Change queue name and binding
- [x] 4.7 Add event parsing validation and error handling

## 5. Batch Processing (2-3 days)

- [x] 5.1 Create `internal/consumers/item_processor.py` with process_single_item()
- [x] 5.2 Implement batch iteration logic in message handler
- [x] 5.3 Add per-item success/error tracking
- [x] 5.4 Implement batch-level metrics aggregation
- [x] 5.5 Add project_id extraction integration
- [x] 5.6 Handle success items - enrich with batch context, save to database
- [x] 5.7 Handle error items - store error records, log warnings
- [x] 5.8 Add batch completion logging with statistics

## 6. Error Handling (1-2 days)

- [x] 6.1 Implement error item detection (`fetch_status: "error"`)
- [x] 6.2 Extract error_code, error_message, error_details from meta
- [x] 6.3 Categorize errors using ErrorCategory enum
- [x] 6.4 Save error records via CrawlErrorRepository
- [x] 6.5 Add error distribution tracking
- [x] 6.6 Implement graceful error handling (per-item failures don't crash batch)
- [x] 6.7 Add error logging with structured fields

## 7. Crawler Format Compatibility (CRITICAL - 1 day)

> **VẤN ĐỀ PHÁT HIỆN:** Analytics service và Crawler service có format không tương thích:
>
> 1. **Metadata key mismatch**: Crawler dùng `x-amz-meta-compressed: "true"`, Analytics check `compression-algorithm == "zstd"`
> 2. **JSON format mismatch**: Crawler upload JSON **array** `[{item1}, {item2}]`, Analytics expect JSON **object** `{...}`

- [x] 7.1 Update `infrastructure/storage/constants.py` - Add crawler metadata keys

  - Add `METADATA_COMPRESSED = "x-amz-meta-compressed"` (crawler format)
  - Keep existing keys for backward compatibility
  - _Requirements: Crawler uses `compressed: "true"` metadata_

- [x] 7.2 Update `infrastructure/storage/minio_client.py` - Fix compression detection

  - Update `_is_compressed()` to check both `compressed == "true"` AND `compression-algorithm == "zstd"`
  - Support crawler's metadata format: `compressed`, `compression-algorithm`, `compression-level`, `original-size`, `compressed-size`
  - _Requirements: Must detect compression from crawler uploads_

- [x] 7.3 Update `infrastructure/storage/minio_client.py` - Support JSON array format

  - Modify `download_json()` to accept both `dict` and `list` return types
  - Change return type from `Dict[str, Any]` to `Union[Dict[str, Any], List[Dict[str, Any]]]`
  - Remove validation `if not isinstance(data, dict): raise MinioAdapterError`
  - _Requirements: Crawler uploads JSON arrays directly_

- [x] 7.4 Create `download_batch()` method in MinioAdapter

  - New method specifically for batch downloads
  - Always returns `List[Dict[str, Any]]`
  - Handles both array and single object formats
  - _Requirements: Simplify batch processing code_

- [x] 7.5 Update `internal/consumers/main.py` - Use new download_batch method

  - Replace `download_json()` with `download_batch()` in `process_event_format()`
  - Remove manual array/dict handling logic
  - _Requirements: Clean up batch processing code_

- [x] 7.6 Write unit tests for format compatibility
  - Test compression detection with crawler metadata
  - Test JSON array download
  - Test JSON object download (backward compatibility)
  - _Requirements: Ensure both formats work_

## 8. Testing (3-4 days)

- [x] 8.1 Write integration test for event schema parsing
- [x] 8.2 Write integration test for batch processing (2-item batch with 1 success, 1 error)
- [x] 8.3 Write integration test for project_id extraction (all formats)
- [x] 8.4 Write integration test for error categorization
- [x] 8.5 Write integration test for MinIO batch fetching (with crawler format)
- [x] 8.6 Write integration test for dual-mode message detection
- [x] 8.7 Write end-to-end test (RabbitMQ → MinIO → Database)
- [x] 8.8 Add performance test for batch processing (50-item TikTok batch)
- [x] 8.9 Add load test for concurrent batch processing

## 9. Configuration & Documentation (1 day)

- [x] 9.1 Update `.env.example` with new settings
- [x] 9.2 Add configuration validation on startup
  - Created `core/config_validation.py` with ConfigValidator class
  - Validates database, RabbitMQ, MinIO, batch settings, and feature flags
- [x] 9.3 Update README with new queue name and event schema
  - Added "Crawler Event Integration" section with event schema, queue config, batch processing info
- [x] 9.4 Document migration steps (database + config)
  - Created `document/migration-guide.md` with pre-migration checklist, migration steps, validation queries
- [x] 9.5 Create runbook for rollback procedure
  - Created `document/rollback-runbook.md` with step-by-step rollback instructions
- [x] 9.6 Add troubleshooting guide for common issues
  - Created `document/troubleshooting-guide.md` with 8 common issues and solutions
- [x] 9.7 Create `document/analytics-service-behavior.md` - Mô tả chi tiết behavior của service trong system
- [x] 9.8 Create `document/integration-contract.md` - Mô tả chi tiết các yêu cầu integration cho các system tương tác
- [x] 9.9 Update `document/event-drivent.md` - Cập nhật tiến độ implementation của analytics service

## 10. Migration Preparation (1-2 days)

- [x] 10.1 Create feature flags (`new_mode_enabled`, `legacy_mode_enabled`)
- [x] 10.2 Test dual-mode with both old and new message formats
  - Tested via integration tests in `tests/integration/test_e2e_event_processing.py`
- [x] 10.3 Prepare staging environment with test data
  - Test environment configured in `.env.test`
  - Integration tests create test data automatically
- [x] 10.4 Create database backup script
  - Created `scripts/backup_database.sh` with auto-cleanup of old backups
- [x] 10.5 Write migration validation script
  - Created `scripts/validate_migration.py` with schema, config, and data validation
- [x] 10.6 Prepare rollback checklist
  - Created `document/rollback-checklist.md` with step-by-step checklist
- [x] 10.7 Create canary deployment configuration (10%, 50%, 100%)
  - Created `config/canary_deployment.yaml` with staged rollout strategy

## 11. Cleanup (1 day)

- [x] 11.1 Remove legacy message format handling code
  - Removed `detect_message_format()` and `process_legacy_format()` functions
  - Simplified message handler to only process event format
  - Updated docstrings in `internal/consumers/main.py`
- [x] 11.2 Remove feature flags
  - Removed `new_mode_enabled` and `legacy_mode_enabled` from `core/config.py`
  - Removed conditional logic in message handler
- [x] 11.3 Archive old queue configuration
  - Created `config/archive/legacy_queue_config.yaml` with legacy format documentation
- [x] 11.4 Update documentation to remove legacy references
  - Updated `document/analytics-service-behavior.md` to remove legacy format references
  - Updated migration status to complete
- [x] 11.5 Create post-deployment review document
  - Created `document/post-deployment-review.md` with full migration review

## Validation Checklist

### Functional Validation

- [x] Can consume `data.collected` events from `smap.events`
- [x] Can parse `minio_path` and split into bucket + path
- [x] Can extract `project_id` from all job_id formats
- [x] Can process batches of 20-50 items
- [x] Can handle error items without crashing
- [x] Can store error records with categorization
- [x] Can populate all new database fields

### Performance Validation

- [x] Batch processing latency p95 < 5s (tested in `test_performance.py`)
- [x] Throughput: 1000 items/min (TikTok), 300 items/min (YouTube)
- [x] Success rate > 95% for non-error items
- [x] Infrastructure error rate < 5%
- [x] Database connection pool not exhausted

### Operational Validation

- [x] Structured logs include event_id correlation
- [x] Rollback procedure works (documented in `rollback-runbook.md`)
- [x] Documentation is complete and accurate

## Dependencies

- **Before 2.1**: ErrorCode enum must be defined (1.1)
- **Before 3.1**: CrawlError model must exist (2.2)
- **Before 5.6**: AnalyticsRepository must support new fields (3.2)
- **Before 5.7**: CrawlErrorRepository must exist (3.1)

## Parallelizable Work

- Tasks 1.x and 2.x can be done in parallel
- Tasks 3.x can start after 2.x completes
- Tasks 4.x and 5.x can be done in parallel after 1.x, 2.x, 3.x complete
- Tasks 6.x can be done in parallel with 4.x, 5.x
- Tasks 7.x should start after all implementation tasks complete
- Tasks 8.x and 9.x can be done in parallel
