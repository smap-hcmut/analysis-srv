# monitoring Specification

## Purpose
TBD - created by archiving change integrate-crawler-events. Update Purpose after archive.
## Requirements
### Requirement: Prometheus Metrics Export

The system SHALL expose Prometheus metrics on HTTP endpoint for monitoring.

#### Scenario: Start metrics HTTP server

- **WHEN** consumer service starts
- **THEN** start Prometheus metrics HTTP server on configured port (default 9090)

#### Scenario: Expose metrics endpoint

- **WHEN** Prometheus scrapes metrics endpoint
- **THEN** return all registered metrics in Prometheus text format

---

### Requirement: Event Consumption Metrics

The system SHALL track event processing metrics for observability.

#### Scenario: Count events received

- **WHEN** `data.collected` event is received
- **THEN** increment `analytics_events_received_total` counter

#### Scenario: Count events processed

- **WHEN** batch processing completes successfully
- **THEN** increment `analytics_events_processed_total` counter with `platform` label

#### Scenario: Count events failed

- **WHEN** batch processing fails with exception
- **THEN** increment `analytics_events_failed_total` counter

#### Scenario: Measure processing duration

- **WHEN** processing `data.collected` event
- **THEN** record duration in `analytics_event_processing_duration_seconds` histogram

---

### Requirement: Batch Processing Metrics

The system SHALL track batch-level metrics for performance monitoring.

#### Scenario: Count batches fetched

- **WHEN** batch array fetched from MinIO
- **THEN** increment `analytics_batches_fetched_total` counter

#### Scenario: Measure batch fetch latency

- **WHEN** fetching batch from MinIO
- **THEN** record duration in `analytics_batch_fetch_duration_seconds` histogram

#### Scenario: Measure batch parse latency

- **WHEN** parsing batch JSON array
- **THEN** record duration in `analytics_batch_parse_duration_seconds` histogram

---

### Requirement: Item Processing Metrics

The system SHALL track item-level metrics with platform and status labels.

#### Scenario: Count items processed

- **WHEN** item processing completes
- **THEN** increment `analytics_items_processed_total{platform, status}` counter

#### Scenario: Track success items

- **WHEN** item with `fetch_status="success"` is processed
- **THEN** increment counter with `status="success"` label

#### Scenario: Track error items

- **WHEN** item with `fetch_status="error"` is processed
- **THEN** increment counter with `status="error"` label

---

### Requirement: Error Distribution Metrics

The system SHALL track error distribution by code and category.

#### Scenario: Count errors by code

- **WHEN** error item is processed
- **THEN** increment `analytics_errors_by_code_total{error_code, platform}` counter

#### Scenario: Count errors by category

- **WHEN** error item is processed
- **THEN** increment `analytics_errors_by_category_total{error_category, platform}` counter

---

### Requirement: Success and Error Rate Gauges

The system SHALL maintain real-time success and error rate metrics.

#### Scenario: Update success rate

- **WHEN** batch processing completes
- **THEN** set `analytics_success_rate{platform}` gauge to `(success_count / total_count) * 100`

#### Scenario: Update error rate

- **WHEN** batch processing completes
- **THEN** set `analytics_error_rate{platform}` gauge to `(error_count / total_count) * 100`

#### Scenario: Handle zero-item batch

- **WHEN** batch contains zero items
- **THEN** do not update rate gauges (avoid division by zero)

---

### Requirement: Infrastructure Metrics

The system SHALL expose infrastructure health metrics.

#### Scenario: Track RabbitMQ connection status

- **WHEN** RabbitMQ connection state changes
- **THEN** set `analytics_rabbitmq_connection_status` gauge to 1 (connected) or 0 (disconnected)

#### Scenario: Track MinIO connection errors

- **WHEN** MinIO fetch operation fails
- **THEN** increment `analytics_minio_connection_errors_total` counter

#### Scenario: Track database connection pool

- **WHEN** querying database connection pool
- **THEN** expose `analytics_database_connection_pool_size` gauge

---

### Requirement: Structured Logging with Correlation

The system SHALL log all events with correlation IDs for tracing.

#### Scenario: Log event received

- **WHEN** `data.collected` event is received
- **THEN** log at INFO level with `event_id`, `project_id`, `job_id`, `batch_index`, `platform`

#### Scenario: Log batch processing completion

- **WHEN** batch processing completes
- **THEN** log at INFO level with `event_id`, `success_count`, `error_count`, `processing_duration_seconds`

#### Scenario: Log item processing errors

- **WHEN** item processing fails with exception
- **THEN** log at ERROR level with `event_id`, `content_id`, `exception_type`, `exception_message`

---

### Requirement: Alerting Metrics

The system SHALL expose metrics suitable for alerting rules.

#### Scenario: High error rate alert

- **WHEN** `analytics_error_rate{platform}` exceeds threshold (e.g., 10%)
- **THEN** Prometheus alert should trigger based on gauge value

#### Scenario: Processing latency alert

- **WHEN** `analytics_event_processing_duration_seconds` p95 exceeds threshold (e.g., 30s)
- **THEN** Prometheus alert should trigger based on histogram percentile

#### Scenario: Connection failure alert

- **WHEN** `analytics_rabbitmq_connection_status` equals 0 for >1 minute
- **THEN** Prometheus alert should trigger for connection loss

### Requirement: Prometheus metrics for batch size mismatches

The consumer MUST expose Prometheus metrics tracking when received batch sizes don't match expected sizes (50 for TikTok, 20 for YouTube). The consumer SHALL increment a counter `analytics_batch_size_mismatch_total` when batch size does not match expected size, with labels for `platform`, `expected_size`, and `actual_size`.

**Rationale:**

- Unexpected batch sizes indicate crawler assembly bugs
- Log-only tracking prevents automated alerting
- Trending helps detect gradual degradation

#### Scenario: Batch with unexpected size increments metric

**Given:**

- Consumer receives batch from TikTok crawler
- Batch contains 45 items (expected: 50)
- Prometheus metrics endpoint is enabled

**When:**

- Consumer processes batch

**Then:**

- Log warning is emitted (existing behavior)
- Prometheus counter `analytics_batch_size_mismatch_total` increments
- Metric has labels: `platform="tiktok"`, `expected_size="50"`, `actual_size="45"`
- Metric is exposed at `:9090/metrics`

**Acceptance:**

```python
# internal/consumers/metrics.py (NEW FILE)
from prometheus_client import Counter

batch_size_mismatch_total = Counter(
    'analytics_batch_size_mismatch_total',
    'Total number of batches with unexpected size',
    ['platform', 'expected_size', 'actual_size']
)

# internal/consumers/main.py:192-199 (MODIFIED)
if len(batch_items) != expected_size:
    logger.warning(
        "Unexpected batch size: expected=%d, actual=%d, platform=%s",
        expected_size, len(batch_items), platform
    )
    # ADD:
    from internal.consumers.metrics import batch_size_mismatch_total
    batch_size_mismatch_total.labels(
        platform=platform,
        expected_size=str(expected_size),
        actual_size=str(len(batch_items))
    ).inc()
```

**Metric Query Examples:**

```promql
# Total mismatches in last 5 minutes
rate(analytics_batch_size_mismatch_total[5m])

# Mismatches by platform
sum(analytics_batch_size_mismatch_total) by (platform)

# Alert on high mismatch rate
rate(analytics_batch_size_mismatch_total[5m]) > 0.1
```

**Validation:**

```bash
# Send test event with incorrect batch size
# Then check metrics
curl http://localhost:9090/metrics | grep analytics_batch_size_mismatch_total

# Should show:
# analytics_batch_size_mismatch_total{platform="tiktok",expected_size="50",actual_size="45"} 1.0
```

---

### Requirement: Prometheus metrics endpoint exposure

The consumer service MUST expose Prometheus metrics on port 9090 (configurable via `metrics_port` setting) for scraping by Prometheus server. The endpoint SHALL be accessible at `http://localhost:{metrics_port}/metrics`, MUST return Prometheus text format, and SHALL include batch size mismatch metrics when `metrics_enabled = true`.

#### Scenario: Metrics endpoint is accessible

**Given:**

- Consumer service is running
- `metrics_enabled = true` in settings
- `metrics_port = 9090` in settings

**When:**

- HTTP GET request to `http://localhost:9090/metrics`

**Then:**

- Response status is 200 OK
- Response contains Prometheus text format
- Batch size mismatch metrics are included
- Standard Python metrics are included (process*\*, python*\*)

**Acceptance:**

```bash
# Verify metrics endpoint
curl -s http://localhost:9090/metrics | head -20

# Should include:
# # HELP analytics_batch_size_mismatch_total Total batches with unexpected size
# # TYPE analytics_batch_size_mismatch_total counter
# analytics_batch_size_mismatch_total{...} 0.0
```

**Configuration:**

```python
# core/config.py (already exists)
metrics_enabled: bool = True
metrics_port: int = 9090
```

---

### Requirement: SentimentAnalyzer Health Check

The system SHALL validate SentimentAnalyzer configuration on startup and provide clear error messages when misconfigured.

#### Scenario: Validate PhoBERT model on startup

- **WHEN** consumer service starts
- **THEN** verify PhoBERT ONNX model is loaded and functional
- **AND** log INFO message confirming sentiment analysis is enabled

#### Scenario: Log error when model not configured

- **WHEN** PhoBERT model fails to load or is not configured
- **THEN** log ERROR message with specific reason (missing model files, invalid path, etc.)
- **AND** continue service startup with sentiment disabled

#### Scenario: Health check endpoint

- **WHEN** health check is requested
- **THEN** include sentiment analyzer status in response (enabled/disabled, model version)

---

### Requirement: Raw Data Debug Logging

The system SHALL provide detailed logging of raw data extracted from crawler events for debugging production issues.

#### Scenario: Log raw event structure

- **WHEN** environment variable `DEBUG_RAW_DATA=true` is set
- **THEN** log complete raw event payload at DEBUG level (sanitized for PII)

#### Scenario: Log extracted item data

- **WHEN** processing individual items from batch
- **THEN** log item ID, platform, and key metadata fields at DEBUG level

#### Scenario: Log analytics result before save

- **WHEN** analytics processing completes for an item
- **THEN** log final analytics payload at DEBUG level before database save

#### Scenario: Sample logging for production

- **WHEN** `DEBUG_RAW_DATA=sample` is set
- **THEN** log detailed data for 1 in every 100 items (sampling)

---

### Requirement: Data Quality Metrics

The system SHALL track and report data quality metrics for monitoring.

#### Scenario: Track metadata completeness

- **WHEN** batch processing completes
- **THEN** calculate and log percentage of records with complete metadata

#### Scenario: Track sentiment analysis coverage

- **WHEN** batch processing completes
- **THEN** log count of records with actual sentiment analysis vs neutral defaults

#### Scenario: Alert on data quality degradation

- **WHEN** metadata completeness drops below 80%
- **THEN** log WARNING indicating potential data quality issue

#### Scenario: Track ID format issues

- **WHEN** batch processing completes
- **THEN** log count of IDs that appear truncated (ending in multiple zeros)

---

### Requirement: Crawler Event Payload Inspection

The system SHALL provide capability to inspect raw crawler event payloads for debugging data extraction issues.

#### Scenario: Log payload field paths

- **WHEN** extracting metadata from event
- **THEN** log which field paths were used (e.g., `payload.job_id` vs `meta.job_id`)

#### Scenario: Log missing expected fields

- **WHEN** expected field is not found in any known location
- **THEN** log WARNING with field name and searched paths

#### Scenario: Log field value types

- **WHEN** `DEBUG_RAW_DATA=true` is set
- **THEN** log data type of each extracted field (string, int, null, etc.)

