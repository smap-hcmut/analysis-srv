# Change: Integrate Crawler Event-Driven Architecture

## Why

The analytics service currently expects single-post messages with a legacy `{data_ref: {bucket, path}}` format, but the crawler services now emit batched `data.collected` events to the `smap.events` exchange. This misalignment prevents the analytics service from consuming crawler data, breaking the end-to-end data pipeline from crawling to analytics.

The event-driven architecture specification (`document/event-drivent.md` and `document/analytics-service-integration-guide.md`) defines a complete choreography pattern where crawlers upload batches of 20-50 items to MinIO and publish events containing metadata (`project_id`, `job_id`, `batch_index`, `minio_path`). The analytics service must be refactored to align with this specification.

## What Changes

This change introduces comprehensive support for the crawler event-driven integration:

### 1. Event Consumption (NEW)

- **ADD** `data.collected` event schema parsing from `smap.events` exchange
- **ADD** RabbitMQ queue binding to `smap.events` with routing key `data.collected`
- **ADD** Event metadata extraction (`event_id`, `timestamp`, `project_id`, `job_id`, `batch_index`, `content_count`)
- **ADD** MinIO path parsing from `payload.minio_path` format (`crawl-results/platform/...`)

### 2. Batch Processing (NEW)

- **ADD** Batch iteration logic to process arrays of 20-50 items per message
- **ADD** Per-item processing with independent error handling
- **ADD** Batch-level success/error metrics and logging
- **ADD** Platform-specific batch size validation (TikTok: 50, YouTube: 20)

### 3. Project ID Extraction (NEW)

- **ADD** Utility function to extract `project_id` from `job_id` patterns
- **ADD** Support for brand format: `proj_xyz-brand-0` → `proj_xyz`
- **ADD** Support for competitor format: `proj_xyz-toyota-5` → `proj_xyz`
- **ADD** Detection of dry-run tasks (UUID job_id) → `project_id = null`

### 4. Error Handling (NEW)

- **ADD** 17 crawler error code constants (ErrorCode enum)
- **ADD** Error categorization (rate_limiting, content, network, parsing, media, storage, generic)
- **ADD** Error item processing for `fetch_status: "error"` items
- **ADD** CrawlError model and repository for error analytics
- **ADD** Error distribution tracking and metrics

### 5. Database Schema Extensions (**BREAKING**)

- **ADD** 10 new fields to `post_analytics` table:
  - `job_id`, `batch_index`, `task_type` (batch context)
  - `keyword_source`, `crawled_at`, `pipeline_version` (crawler metadata)
  - `fetch_status`, `fetch_error`, `error_code`, `error_details` (error tracking)
- **ADD** New `crawl_errors` table with indexes
- **ADD** Alembic migration for schema updates

### 6. Configuration Updates

- **ADD** Event queue settings (`event_exchange`, `event_routing_key`, `event_queue_name`)
- **ADD** Batch processing settings (`max_concurrent_batches`, `batch_timeout_seconds`)
- **ADD** Error code lists (`permanent_error_codes`, `transient_error_codes`)
- **ADD** MinIO crawl results bucket configuration

### 7. Monitoring & Metrics (NEW)

- **ADD** Prometheus metrics for events, batches, items, errors
- **ADD** Success/error rate gauges per platform
- **ADD** Error distribution counters by error code and category
- **ADD** Batch processing duration histograms

### 8. Backward Compatibility

- **MODIFY** Message handler to support dual-mode processing (old + new formats)
- **ADD** Auto-detection of message format (event vs legacy)
- **ADD** Feature flags for gradual rollout

## Impact

### Affected Specifications

- **NEW**: `event_consumption` - RabbitMQ event handling
- **NEW**: `batch_processing` - Multi-item processing
- **NEW**: `error_handling` - Crawler error management
- **NEW**: `crawler_metadata` - Job/batch tracking
- **NEW**: `monitoring` - Metrics and observability
- **MODIFIED**: `service_lifecycle` - Consumer initialization
- **MODIFIED**: `storage` - MinIO path parsing
- **MODIFIED**: `foundation` - Database schema

### Affected Code

- `internal/consumers/main.py` - Complete message handler rewrite
- `internal/consumers/item_processor.py` - **NEW** per-item processing
- `utils/project_id_extractor.py` - **NEW** extraction logic
- `core/constants.py` - **ADD** ErrorCode and ErrorCategory enums
- `core/config.py` - **ADD** 10+ new settings
- `models/database.py` - **ADD** 10 fields to PostAnalytics, **NEW** CrawlError model
- `repository/crawl_error_repository.py` - **NEW** error data access
- `repository/analytics_repository.py` - **MODIFY** save method for new fields
- `infrastructure/messaging/rabbitmq.py` - **MODIFY** queue binding
- `command/consumer/main.py` - **MODIFY** queue name and binding
- `internal/consumers/metrics.py` - **NEW** Prometheus metrics
- `migrations/` - **NEW** Alembic migration

### Breaking Changes

- **BREAKING**: Database schema requires migration before deployment
- **BREAKING**: RabbitMQ queue name changes from `analytics_queue` to `analytics.data.collected`
- **BREAKING**: MinIO path parsing changes (split bucket from full path)

### Migration Path

1. **Phase 1**: Deploy code with dual-mode support (both old and new formats)
2. **Phase 2**: Run database migration in staging
3. **Phase 3**: Test with mock `data.collected` events
4. **Phase 4**: Canary rollout (10% → 50% → 100%)
5. **Phase 5**: Deprecate legacy message format after 1 month
6. **Phase 6**: Remove dual-mode code

### Rollback Plan

- Feature flags allow instant revert to legacy mode
- No data loss: messages remain in queue for replay
- Database migration can be rolled back via Alembic downgrade

## Dependencies

### External

- Crawler services must be emitting `data.collected` events (✅ Complete per `document/event-drivent.md`)
- MinIO must contain batch files at paths referenced in events (✅ Implemented)
- RabbitMQ `smap.events` exchange must exist (✅ Configured)

### Internal

- Database migration must complete before consumer restart
- Prometheus must be available for metrics (optional, graceful degradation)
- Configuration must be updated with new settings

## Risk Assessment

| Risk                                       | Severity | Mitigation                                                  |
| ------------------------------------------ | -------- | ----------------------------------------------------------- |
| Data loss during migration                 | HIGH     | Dual-mode support, message persistence, replay capability   |
| Performance degradation (batch processing) | MEDIUM   | Load testing, batch size tuning, connection pooling         |
| Database migration failure                 | MEDIUM   | Test on staging, backup before production, rollback script  |
| Incorrect project_id extraction            | MEDIUM   | 100% test coverage, validation with real job_ids in staging |
| Message format detection errors            | LOW      | Explicit format checks, fallback to legacy, error logging   |

## Success Criteria

### Functional

- ✅ Consumes `data.collected` events from `smap.events` exchange
- ✅ Processes batches of 20-50 items per message
- ✅ Extracts `project_id` from all job_id formats with 100% accuracy
- ✅ Handles error items (`fetch_status: "error"`) without pipeline crashes
- ✅ Stores error records with proper categorization
- ✅ Populates all new database fields correctly

### Performance

- ✅ Throughput: 1000 items/min (TikTok), 300 items/min (YouTube)
- ✅ Latency: Batch processing p95 < 5 seconds
- ✅ Success rate: > 95% for non-error items
- ✅ Infrastructure error rate: < 5%

### Operational

- ✅ All Prometheus metrics emitting correctly
- ✅ Structured logs with event correlation IDs
- ✅ Alerts configured for error rate, latency, database health
- ✅ Documentation updated (README, API docs, runbooks)

## Estimated Effort

- **Development**: 12-15 days
- **Testing**: 3-5 days
- **Migration & Rollout**: 5-7 days
- **Total**: 20-25 days (4-5 weeks)

## References

- Gap Analysis: `document/current_gaps.md`
- Event Specification: `document/event-drivent.md`
- Integration Guide: `document/analytics-service-integration-guide.md`
- Project Context: `openspec/project.md`
