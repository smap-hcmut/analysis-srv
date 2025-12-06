# Capability: Monitoring

## ADDED Requirements

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
