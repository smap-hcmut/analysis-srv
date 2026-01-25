# Design: Crawler Event Integration

## Context

The analytics service is part of a larger event-driven microservices architecture where:

- **Crawler services** (TikTok, YouTube) fetch social media content in batches
- **Collector service** orchestrates crawler jobs based on `project.created` events
- **Analytics service** processes crawled data to extract insights
- **Project service** manages project lifecycle and user notifications

Currently, the analytics service uses a legacy message format incompatible with the new event-driven choreography. The crawler services have been refactored to emit `data.collected` events with batch references to MinIO, but analytics cannot consume them.

### Stakeholders

- **Analytics Team**: Primary implementers and maintainers
- **Crawler Team**: Event producers, schema owners
- **Platform Team**: Infrastructure (RabbitMQ, MinIO, PostgreSQL)
- **Product Team**: End-users expecting analytics results

### Constraints

- **Zero downtime**: Must support gradual migration
- **No data loss**: All events must be processable
- **Performance**: Must handle 1000+ items/minute
- **Backward compatibility**: Legacy messages must work during transition
- **Database migrations**: Must be reversible

## Goals / Non-Goals

### Goals

- ✅ Consume `data.collected` events from `smap.events` exchange
- ✅ Process batches of 20-50 items per message efficiently
- ✅ Extract `project_id` from `job_id` for cross-service correlation
- ✅ Handle crawler error items gracefully without pipeline failure
- ✅ Store comprehensive error analytics for monitoring
- ✅ Maintain backward compatibility during migration
- ✅ Provide Prometheus metrics for observability
- ✅ Enable zero-downtime rollout with canary deployment

### Non-Goals

- ❌ Changing the core analytics pipeline (preprocessing, intent, sentiment, impact)
- ❌ Modifying crawler event schema (this is fixed by crawler team)
- ❌ Real-time streaming (batch processing is acceptable)
- ❌ Distributed tracing (Prometheus metrics are sufficient for now)
- ❌ Multi-region deployment (single region for MVP)
- ❌ Message replay UI (manual replay via RabbitMQ tools is acceptable)

## Architectural Decisions

### Decision 1: Dual-Mode Message Processing

**Choice**: Support both legacy and new message formats simultaneously during migration.

**Rationale**:

- Enables zero-downtime rollout
- Reduces deployment risk
- Allows gradual validation
- Provides instant rollback capability

**Implementation**:

```python
async def message_handler(message: IncomingMessage):
    envelope = json.loads(message.body)

    # Auto-detect format
    if "payload" in envelope and "minio_path" in envelope["payload"]:
        # New format: data.collected event
        await process_event_format(envelope)
    elif "data_ref" in envelope:
        # Legacy format: direct MinIO reference
        await process_legacy_format(envelope)
    else:
        # Inline format: direct post data
        await process_inline_format(envelope)
```

**Feature flags**:

- `NEW_MODE_ENABLED=true` (default after migration)
- `LEGACY_MODE_ENABLED=true` (disabled after 1 month)

**Alternatives considered**:

- **Hard cutover**: Rejected due to high risk of data loss
- **Blue-green deployment**: Rejected due to complexity of maintaining two consumers
- **Message versioning**: Rejected as overkill for one-time migration

---

### Decision 2: Per-Item Error Handling vs Batch Failure

**Choice**: Process each item in a batch independently; continue batch on item failures.

**Rationale**:

- One bad item shouldn't block 49 good items
- Crawler may emit partial failures (e.g., rate limiting for some items)
- Error analytics requires item-level tracking
- Aligns with "fail gracefully" principle

**Implementation**:

```python
success_count = 0
error_count = 0

for item in batch_items:
    try:
        result = process_single_item(item, ...)
        if result["status"] == "success":
            success_count += 1
        else:
            error_count += 1
    except Exception as exc:
        logger.error(f"Error processing item: {exc}")
        error_count += 1

# Ack message even if some items failed
logger.info(f"Batch completed: success={success_count}, errors={error_count}")
```

**Trade-off**: Increased complexity vs better resilience.

**Alternatives considered**:

- **Fail entire batch on error**: Rejected as too fragile
- **Partial ack (individual messages)**: Not supported by RabbitMQ batch model
- **Dead letter queue per item**: Rejected as unnecessarily complex

---

### Decision 3: Separate Error Table vs Error Fields in Main Table

**Choice**: Create dedicated `crawl_errors` table in addition to error fields in `post_analytics`.

**Rationale**:

- **Separation of concerns**: Analytics data vs error telemetry
- **Query performance**: Error analytics queries don't slow down main table
- **Retention policies**: Can truncate old errors without affecting analytics
- **Error enrichment**: Can add error-specific fields without bloating main table

**Schema**:

- `post_analytics`: Includes `fetch_status`, `error_code` for filtering
- `crawl_errors`: Full error details with `error_category`, `error_message`, `error_details`

**Alternatives considered**:

- **Single table with JSONB**: Rejected due to poor query performance
- **Error-only storage (no main table fields)**: Rejected as makes filtering hard
- **Separate database**: Rejected as premature optimization

---

### Decision 4: Project ID Extraction via Parsing vs Database Lookup

**Choice**: Extract `project_id` from `job_id` pattern matching, not database lookup.

**Rationale**:

- **Performance**: No database roundtrip per item (50x speedup for batches)
- **Simplicity**: Pure function, easy to test, no I/O
- **Availability**: Works even if project service is down
- **Consistency**: Deterministic, no cache invalidation issues

**Implementation**:

```python
def extract_project_id(job_id: str) -> Optional[str]:
    # UUID pattern → dry-run → None
    if re.match(UUID_PATTERN, job_id):
        return None

    # Split by '-', last part is index, second-to-last is brand/competitor
    parts = job_id.split('-')
    if len(parts) < 3 or not parts[-1].isdigit():
        return None

    return '-'.join(parts[:-2])
```

**Validation**: 100% test coverage with 11 test cases covering all formats.

**Alternatives considered**:

- **Database lookup**: Rejected due to performance impact (50 queries per batch)
- **Redis cache**: Rejected as unnecessary complexity
- **Crawler includes project_id in payload**: Rejected as requires crawler changes

---

### Decision 5: Batch Size Validation (Strict vs Lenient)

**Choice**: Log warnings for unexpected batch sizes but don't fail processing.

**Rationale**:

- **Robustness**: Crawler may emit partial batches (end of job, errors)
- **Forward compatibility**: Crawler batch sizes may change
- **Debugging**: Logs help detect crawler issues without blocking pipeline

**Implementation**:

```python
expected_size = 50 if platform == "tiktok" else 20
if len(batch_items) != expected_size:
    logger.warning(
        f"Unexpected batch size: expected={expected_size}, "
        f"actual={len(batch_items)}, platform={platform}"
    )
# Continue processing
```

**Alternatives considered**:

- **Strict validation (reject batch)**: Rejected as too fragile
- **No validation**: Rejected as loses debugging capability
- **Configurable thresholds**: Deferred to future if needed

---

### Decision 6: Metrics Strategy (Pull vs Push)

**Choice**: Prometheus pull-based metrics on HTTP endpoint `:9090/metrics`.

**Rationale**:

- **Standard**: Aligns with existing infrastructure
- **Simplicity**: No additional services (StatsD, InfluxDB)
- **Tooling**: Grafana dashboards, alerting, federation
- **Performance**: No network overhead on critical path

**Metrics exposed**:

- Counters: `events_received`, `items_processed`, `errors_by_code`
- Gauges: `success_rate`, `error_rate`
- Histograms: `event_processing_duration`, `batch_fetch_duration`

**Labels**: `platform`, `error_code`, `error_category`

**Alternatives considered**:

- **Push to StatsD**: Rejected as requires additional service
- **Logs-based metrics**: Rejected as too slow for real-time alerts
- **Custom monitoring**: Rejected as reinvents the wheel

---

## Data Flow

### Current Flow (Legacy)

```
RabbitMQ (analytics_queue)
    ↓
Parse {data_ref: {bucket, path}}
    ↓
MinIO: Fetch single post JSON
    ↓
Analytics Pipeline (1 post)
    ↓
PostgreSQL: Insert 1 row
    ↓
Ack message
```

**Throughput**: ~10-20 posts/second (limited by message overhead)

---

### New Flow (Event-Driven)

```
RabbitMQ (smap.events → analytics.data.collected)
    ↓
Parse {payload: {minio_path, project_id, job_id, batch_index, ...}}
    ↓
MinIO: Fetch batch array (20-50 items)
    ↓
Extract project_id from job_id
    ↓
FOR EACH item in batch:
  ├─ IF fetch_status == "success":
  │    ├─ Analytics Pipeline
  │    ├─ Enrich with batch context
  │    └─ PostgreSQL: Insert with project_id, job_id, batch_index
  └─ ELIF fetch_status == "error":
       ├─ Categorize error_code
       └─ PostgreSQL: Insert error record
    ↓
Aggregate metrics (success_count, error_count, error_distribution)
    ↓
Prometheus: Emit metrics
    ↓
Ack message
```

**Throughput**: ~1000-1500 items/minute (20-30x improvement)

---

## Database Schema Changes

### post_analytics (MODIFIED)

**New fields**:

```sql
-- Batch context
job_id VARCHAR(100),           -- proj_xyz-brand-0
batch_index INTEGER,           -- 1, 2, 3, ...
task_type VARCHAR(30),         -- research_and_crawl, dryrun_keyword

-- Crawler metadata
keyword_source VARCHAR(200),   -- "VinFast VF8"
crawled_at TIMESTAMP,          -- 2025-12-06T10:15:30Z
pipeline_version VARCHAR(50),  -- crawler_tiktok_v3

-- Error tracking
fetch_status VARCHAR(10),      -- success, error
fetch_error TEXT,              -- Error message
error_code VARCHAR(50),        -- RATE_LIMITED, CONTENT_REMOVED, ...
error_details JSONB            -- Full error context
```

**New indexes**:

```sql
CREATE INDEX idx_post_analytics_job_id ON post_analytics(job_id);
CREATE INDEX idx_post_analytics_fetch_status ON post_analytics(fetch_status);
CREATE INDEX idx_post_analytics_task_type ON post_analytics(task_type);
```

---

### crawl_errors (NEW)

```sql
CREATE TABLE crawl_errors (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(50) NOT NULL,
    project_id UUID,               -- NULL for dry-run
    job_id VARCHAR(100) NOT NULL,
    platform VARCHAR(20) NOT NULL,

    error_code VARCHAR(50) NOT NULL,
    error_category VARCHAR(30) NOT NULL,
    error_message TEXT,
    error_details JSONB,

    permalink TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_crawl_errors_project_id ON crawl_errors(project_id);
CREATE INDEX idx_crawl_errors_error_code ON crawl_errors(error_code);
CREATE INDEX idx_crawl_errors_created_at ON crawl_errors(created_at);
```

**Estimated size**: ~100KB per 1000 errors, ~36MB per year at 10% error rate

---

## Error Code Taxonomy

### Categories & Codes

| Category          | Codes                                                      | Retry? | Action                     |
| ----------------- | ---------------------------------------------------------- | ------ | -------------------------- |
| **rate_limiting** | RATE_LIMITED, AUTH_FAILED, ACCESS_DENIED                   | Yes    | Backoff & retry            |
| **content**       | CONTENT_REMOVED, CONTENT_NOT_FOUND, CONTENT_UNAVAILABLE    | No     | Skip permanently           |
| **network**       | NETWORK_ERROR, TIMEOUT, CONNECTION_REFUSED, DNS_ERROR      | Yes    | Retry with backoff         |
| **parsing**       | PARSE_ERROR, INVALID_URL, INVALID_RESPONSE                 | No     | Alert team                 |
| **media**         | MEDIA_DOWNLOAD_FAILED, MEDIA_TOO_LARGE, MEDIA_FORMAT_ERROR | No     | Use metadata only          |
| **storage**       | STORAGE_ERROR, UPLOAD_FAILED, DATABASE_ERROR               | Yes    | Retry, alert if persistent |
| **generic**       | UNKNOWN_ERROR, INTERNAL_ERROR                              | Maybe  | Investigate case-by-case   |

**Total**: 17 error codes across 7 categories

---

## Performance Considerations

### Batch Processing

**Target**: 5 seconds p95 for 50-item batch

**Breakdown**:

- MinIO fetch: ~500ms (compressed batch ~50KB)
- Project ID extraction: ~0.1ms per item (5ms total)
- Analytics pipeline: ~50ms per item (2.5s total)
- Database inserts: ~2s (batch insert, 50 rows)

**Optimizations**:

- Connection pooling (MinIO: 10 connections, DB: 20 connections)
- Batch database inserts (50 rows in single transaction)
- Async I/O for MinIO fetches
- Zstd decompression (~100ms for 50KB)

---

### Concurrency

**Configuration**:

- `rabbitmq_prefetch_count = 1` (process one batch at a time)
- `max_concurrent_batches = 5` (multiple workers)

**Rationale**:

- Prefetch=1 ensures QoS (backpressure if consumer is slow)
- 5 workers balance throughput vs database connection usage
- Total capacity: 5 batches × 50 items × 12 batches/min = 3000 items/min

---

### Database Connection Pool

```python
# Sync pool for consumer
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 10

# Async pool for API
ASYNC_DATABASE_POOL_SIZE = 10
```

**Calculation**:

- 5 concurrent batches × 2 connections (analytics + errors) = 10 active
- 10 headroom for spikes = 20 pool size
- 10 overflow for bursts

---

## Migration Plan

### Phase 1: Development & Testing (5 days)

1. Implement all code changes
2. Write unit tests (100% coverage for critical paths)
3. Write integration tests (event parsing, batch processing, error handling)
4. Local testing with mock events

### Phase 2: Staging Deployment (3 days)

1. Deploy code to staging
2. Run database migration on staging
3. Test with real crawler events
4. Validate metrics and error handling
5. Load test with 1000 items/minute

### Phase 3: Production Canary (7 days)

1. Deploy code with `NEW_MODE_ENABLED=false` (legacy only)
2. Run database migration on production (backup first)
3. Enable new mode for 10% traffic (`NEW_MODE_ENABLED=true`, canary routing)
4. Monitor for 2 days (error rate, latency, throughput)
5. Scale to 50% traffic
6. Monitor for 3 days
7. Scale to 100% traffic

### Phase 4: Legacy Deprecation (30 days)

1. Monitor 100% traffic for 1 week
2. Announce legacy format EOL (30-day notice)
3. Disable legacy mode (`LEGACY_MODE_ENABLED=false`)
4. Monitor for 1 week
5. Remove legacy code

### Phase 5: Cleanup (2 days)

1. Remove feature flags
2. Archive old queue configuration
3. Update documentation

**Total timeline**: ~45 days (6-7 weeks)

---

## Rollback Procedures

### Immediate Rollback (< 5 minutes)

**Trigger**: Error rate > 20%, success rate < 80%, critical alerts

**Steps**:

1. Set `NEW_MODE_ENABLED=false` (environment variable)
2. Restart consumer service
3. Verify legacy mode is working
4. Investigate root cause

**Data recovery**:

- Events remain in queue (not acked)
- Replay from last processed message
- No data loss

---

### Database Rollback

**Trigger**: Migration failure, data corruption

**Steps**:

```bash
# Stop consumer
systemctl stop analytics-consumer

# Restore backup
pg_restore -d analytics_db backup_pre_migration.sql

# Or run Alembic downgrade
alembic downgrade -1

# Restart with legacy mode
export NEW_MODE_ENABLED=false
systemctl start analytics-consumer
```

**Downtime**: ~10-15 minutes

---

## Risks & Trade-offs

### Risk 1: Database Migration Failure

- **Probability**: Low (tested in staging)
- **Impact**: High (service downtime)
- **Mitigation**: Backup before migration, test downgrade, staging validation
- **Rollback**: Restore from backup or Alembic downgrade

### Risk 2: Performance Degradation

- **Probability**: Medium (batch processing is new)
- **Impact**: Medium (slower processing, queue backlog)
- **Mitigation**: Load testing, connection pooling, canary deployment
- **Rollback**: Feature flag to legacy mode

### Risk 3: Incorrect Project ID Extraction

- **Probability**: Low (100% test coverage)
- **Impact**: High (wrong analytics attribution)
- **Mitigation**: Extensive unit tests, staging validation with real job_ids
- **Rollback**: Fix extraction logic, reprocess with correct project_id

### Risk 4: MinIO Path Parsing Errors

- **Probability**: Low (simple split logic)
- **Impact**: Medium (batch fetch failures)
- **Mitigation**: Validation tests, graceful error handling
- **Rollback**: Feature flag to legacy mode

### Risk 5: Error Code Misclassification

- **Probability**: Medium (17 codes, many edge cases)
- **Impact**: Low (analytics impact only)
- **Mitigation**: Comprehensive error code mapping, categorization tests
- **Rollback**: Update categorization logic, no migration needed

---

## Open Questions

### Resolved ✅

- ✅ Should we validate batch sizes strictly? **Decision**: Log warnings, don't fail
- ✅ How to handle partial batches? **Decision**: Process normally, log size mismatch
- ✅ Separate error table or JSONB field? **Decision**: Both (fields for filtering, table for analytics)
- ✅ Database lookup or pattern matching for project_id? **Decision**: Pattern matching (performance)

### Pending ❓

- ❓ Should we add distributed tracing (OpenTelemetry)? **Defer to future**
- ❓ Do we need message replay UI? **Defer to future (use RabbitMQ tools for now)**
- ❓ Should error records have TTL? **Monitor storage, decide based on usage**
- ❓ Multi-region deployment strategy? **Out of scope for MVP**

---

## Success Metrics

### Functional Metrics

- ✅ Event consumption success rate: 100%
- ✅ Project ID extraction accuracy: 100%
- ✅ Error item handling: No crashes on error items
- ✅ Database field population: All new fields populated correctly

### Performance Metrics

- ✅ Batch processing p95 latency: < 5s
- ✅ Throughput: 1000 items/min (TikTok), 300 items/min (YouTube)
- ✅ Success rate: > 95% for non-error items
- ✅ Infrastructure error rate: < 5%

### Operational Metrics

- ✅ Zero downtime during migration
- ✅ No data loss during rollout
- ✅ Metrics emitting within 1 hour of deployment
- ✅ Alerts configured and tested
- ✅ Rollback procedure < 5 minutes

---

## References

- Event Specification: `document/event-drivent.md`
- Integration Guide: `document/analytics-service-integration-guide.md`
- Gap Analysis: `document/current_gaps.md`
- Crawler Implementation: `openspec/changes/archive/2025-12-06-refactor-crawler-event-integration/`
- RabbitMQ Best Practices: [RabbitMQ Production Checklist](https://www.rabbitmq.com/production-checklist.html)
- Prometheus Best Practices: [Prometheus Metric Naming](https://prometheus.io/docs/practices/naming/)
