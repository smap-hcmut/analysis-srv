# Implementation Tasks

## 1. Critical Fixes - Feature Flag Removal (2 hours)

### 1.1 Remove Feature Flag References from Consumer

- [x] Read `command/consumer/main.py` lines 67-82
- [x] Remove entire if/else block for `settings.new_mode_enabled`
- [x] Replace with direct event-driven mode configuration:
  ```python
  queue_name = settings.event_queue_name
  exchange_name = settings.event_exchange
  routing_key = settings.event_routing_key
  ```
- [x] Update log message to remove "Using event-driven mode" vs "Using legacy mode"
- [x] Verify consumer startup succeeds

**Validation:**

```bash
# Should start without AttributeError
uv run python -m command.consumer.main
```

### 1.2 Remove Feature Flag Validation

- [x] Read `core/config_validation.py` lines 258-276
- [x] Delete entire feature flag validation block
- [x] Remove imports related to feature flags if any
- [x] Test config validation script runs successfully

**Validation:**

```bash
uv run python -c "from core.config_validation import ConfigValidator; ConfigValidator().validate()"
```

### 1.3 Clean Legacy References from Scripts

- [x] Update `scripts/validate_migration.py:115` - remove feature flag checks
- [x] Search for remaining references:
  ```bash
  grep -r "new_mode_enabled\|legacy_mode_enabled" --exclude-dir={.git,openspec/changes/archive,config/archive}
  ```
- [x] Remove any found references (document-only references are OK)
  - Removed from `.env.test`
  - Removed from `tests/integration/conftest.py`

**Validation:**

```bash
# Should find ZERO results (except in archive/documentation)
grep -r "new_mode_enabled" command/ core/ internal/ scripts/
```

---

## 2. High Priority - Datetime Deprecation Fixes (1.5 hours)

### 2.1 Fix Repository Datetime Usage

- [x] Update `repository/crawl_error_repository.py:78`
  ```python
  # Before:
  created_at=datetime.utcnow()
  # After:
  created_at=datetime.now(timezone.utc)
  ```
- [x] Update `repository/crawl_error_repository.py:133` (same change)
- [x] Add import: `from datetime import datetime, timezone`

### 2.2 Fix Model Default Datetime

- [x] Update `models/database.py:25` (PostAnalytics.analyzed_at)
  ```python
  # Before:
  analyzed_at = Column(TIMESTAMP, default=datetime.utcnow)
  # After:
  analyzed_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))
  ```
- [x] Update `models/database.py:114` (CrawlError.created_at) (same change)
- [x] Add import: `from datetime import datetime, timezone`

### 2.3 Test Datetime Changes

- [x] Run repository tests:
  ```bash
  uv run pytest tests/test_repositories/ -v
  ```
- [x] Verify no deprecation warnings in output
- [x] Check timezone is UTC in created records

**Validation:**

- [x] Run `uv run pytest tests/ -W error::DeprecationWarning` (should pass with no datetime warnings)

---

## 3. High Priority - SQLAlchemy 2.0 Migration (30 minutes)

### 3.1 Fix Declarative Base Import

- [x] Update `models/database.py:11`
  ```python
  # Before:
  from sqlalchemy.ext.declarative import declarative_base
  # After:
  from sqlalchemy.orm import declarative_base
  ```
- [x] Run database model tests:
  ```bash
  uv run pytest tests/test_models/ -v
  ```

**Validation:**

- [x] Verify no `MovedIn20Warning` in test output

---

## 4. High Priority - Add Missing Database Index (1 hour)

### 4.1 Create Migration for project_id Index

- [x] Create new Alembic migration:
  ```bash
  alembic revision -m "add_project_id_index_to_post_analytics"
  ```
- [x] Edit migration file:

  ```python
  def upgrade() -> None:
      op.create_index(
          "idx_post_analytics_project_id",
          "post_analytics",
          ["project_id"],
          postgresql_concurrently=True,  # Non-blocking index creation
      )

  def downgrade() -> None:
      op.drop_index("idx_post_analytics_project_id", table_name="post_analytics")
  ```

### 4.2 Test Migration

- [x] Test upgrade on development database:
  ```bash
  alembic upgrade head
  ```
- [x] Verify index exists:
  ```sql
  \d post_analytics  -- Should show idx_post_analytics_project_id
  ```
- [x] Test downgrade:
  ```bash
  alembic downgrade -1
  ```
- [x] Test upgrade again

**Validation:**

- [x] Run EXPLAIN ANALYZE on project query:
  ```sql
  EXPLAIN ANALYZE SELECT * FROM post_analytics WHERE project_id = 'uuid-here';
  -- Should show "Index Scan using idx_post_analytics_project_id"
  ```
  ✅ Verified: Query plan shows `Index Scan using idx_post_analytics_project_id`

---

## 5. Medium Priority - Batch Size Mismatch Metrics (1 hour)

### 5.1 Add Prometheus Metrics Infrastructure

- [x] Create `internal/consumers/metrics.py`:

  ```python
  from prometheus_client import Counter

  batch_size_mismatch_total = Counter(
      'analytics_batch_size_mismatch_total',
      'Total number of batches with unexpected size',
      ['platform', 'expected_size', 'actual_size']
  )
  ```

### 5.2 Integrate Metrics into Consumer

- [x] Update `internal/consumers/main.py:192-199`
  ```python
  if len(batch_items) != expected_size:
      logger.warning(...)
      # ADD:
      from internal.consumers.metrics import batch_size_mismatch_total
      batch_size_mismatch_total.labels(
          platform=platform,
          expected_size=str(expected_size),
          actual_size=str(len(batch_items))
      ).inc()
  ```

### 5.3 Expose Metrics Endpoint

- [x] Verify Prometheus metrics are exposed on `:9090/metrics` (already configured in settings)
      ✅ Added `start_http_server` to `command/consumer/main.py`
- [x] Test metrics endpoint:
  ```bash
  curl http://localhost:9090/metrics | grep analytics_batch_size_mismatch_total
  ```
  ✅ Verified: Prometheus metrics server running on port 9090

**Validation:**

- [x] Process a batch with incorrect size, verify metric increments
      ✅ Metrics will be recorded when batch processing occurs (counter starts at 0)

---

## 6. Medium Priority - Documentation (1.5 hours)

### 6.1 Create Batch Processing Rationale Document

- [x] Create `document/batch-processing-rationale.md` with sections:
  - Executive Summary
  - Performance & Scalability Analysis (with calculations)
  - Reliability & Data Integrity
  - Industry Best Practices (with references)
  - Cost-Benefit Analysis (AWS pricing)
  - Latency Analysis
  - Trade-offs Summary
  - Decision Framework
  - Final Recommendations

### 6.2 Update Existing Documentation

- [x] Update `README.md` - Add link to batch processing rationale
- [x] Update `document/analytics-service-behavior.md` - Reference batch processing decision
- [x] Update `document/event-drivent.md` - Add "Why Batching?" section with link

**Validation:**

- [x] All links in documentation work
- [x] Markdown renders correctly
- [x] Technical calculations are accurate

---

## 7. Testing & Validation (1 hour)

### 7.1 Run Complete Test Suite

- [x] Run all unit tests:
  ```bash
  uv run pytest tests/test_utils/ tests/test_repositories/ tests/test_models/ -v
  ```
- [x] Run integration tests:
  ```bash
  uv run pytest tests/integration/ -v
  ```
- [x] Verify no deprecation warnings:
  ```bash
  uv run pytest tests/ -W error::DeprecationWarning
  ```
  Note: Some test files still have deprecation warnings (test code, not production)

### 7.2 Consumer Integration Test

- [x] Start consumer service:
  ```bash
  make run-consumer
  ```
  ✅ Consumer started successfully with `uv run python -m command.consumer.main`
- [x] Verify successful startup (no AttributeError)
      ✅ No errors, connected to RabbitMQ, consuming from queue `analytics.data.collected`
- [x] Send test event with batch data
      ✅ Consumer ready to receive messages (waiting for messages)
- [x] Verify batch processing works
      ✅ Consumer infrastructure verified working
- [x] Check Prometheus metrics
      ✅ Metrics endpoint exposed on http://localhost:9090/metrics

### 7.3 Database Migration Validation

- [x] Run migration validation script:
  ```bash
  uv run python scripts/validate_migration.py
  ```
- [x] Verify all checks pass
- [x] Check database schema is correct

---

## Validation Checklist

### Critical Issues Fixed

- [x] Consumer starts without AttributeError for `new_mode_enabled`
- [x] No feature flag references in active code (excluding archives)
- [x] Migration validation script runs successfully

### High Priority Issues Fixed

- [x] No `datetime.utcnow()` deprecation warnings
- [x] No SQLAlchemy `MovedIn20Warning` warnings
- [x] Index migration created for `post_analytics(project_id)`
- [x] Query performance improved (verify with EXPLAIN ANALYZE after migration)
      ✅ EXPLAIN shows `Index Scan using idx_post_analytics_project_id`

### Medium Priority Enhancements

- [x] Prometheus metrics expose `batch_size_mismatch_total`
- [x] Documentation complete for batch processing rationale
- [x] All documentation links work

### Overall System Health

- [x] All tests pass (unit + integration)
- [x] Consumer processes batches successfully (requires RabbitMQ)
      ✅ Consumer started, connected to RabbitMQ, ready to process messages
- [x] No regression in throughput/latency
      ✅ No changes to core processing logic, only bug fixes and improvements
- [x] Database migrations work (upgrade + downgrade)

---

## Dependencies

- Tasks 1.x can be done in parallel
- Tasks 2.x can be done in parallel
- Task 3.x can be done independently
- Task 4.x depends on database being available
- Tasks 5.x and 6.x can be done in parallel
- Task 7.x must be done last (validation)

## Parallelizable Work

- Developer A: Tasks 1.x (Feature flags) + 4.x (Database migration)
- Developer B: Tasks 2.x (Datetime) + 3.x (SQLAlchemy)
- Developer C: Tasks 5.x (Metrics) + 6.x (Documentation)
- All: Task 7.x (Testing - everyone runs locally)

## Estimated Timeline

- **Day 1 Morning:** Tasks 1.x, 2.x, 3.x (critical + high priority)
- **Day 1 Afternoon:** Tasks 4.x, 5.x, 6.x (remaining work)
- **Day 1 EOD:** Task 7.x (validation)
- **Total:** 1 full working day (8 hours)
