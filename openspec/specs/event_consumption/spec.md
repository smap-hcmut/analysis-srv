# event_consumption Specification

## Purpose
TBD - created by archiving change integrate-crawler-events. Update Purpose after archive.
## Requirements
### Requirement: Data Collected Event Parsing

The system SHALL consume `data.collected` events from the `smap.events` RabbitMQ exchange with routing key `data.collected`.

#### Scenario: Parse valid event

- **WHEN** a `data.collected` event is received with all required fields
- **THEN** extract `event_id`, `timestamp`, and payload fields (`project_id`, `job_id`, `platform`, `minio_path`, `content_count`, `batch_index`)

#### Scenario: Handle malformed event

- **WHEN** a `data.collected` event is missing required fields
- **THEN** log validation error and nack message for retry

#### Scenario: Handle invalid JSON

- **WHEN** message body contains invalid JSON
- **THEN** log parsing error and nack message without retry

---

### Requirement: Exchange and Queue Binding

The system SHALL bind queue `analytics.data.collected` to exchange `smap.events` with routing key `data.collected`.

#### Scenario: Queue declaration on startup

- **WHEN** consumer service starts
- **THEN** declare durable queue `analytics.data.collected` and bind to `smap.events` exchange

#### Scenario: Queue already exists

- **WHEN** queue `analytics.data.collected` already exists with different bindings
- **THEN** verify binding to `smap.events` and log warning if mismatched

---

### Requirement: MinIO Path Parsing

The system SHALL parse `minio_path` field from event payload and split into bucket and object path.

#### Scenario: Parse standard path format

- **WHEN** `minio_path` is `"crawl-results/tiktok/proj_xyz/brand/batch_000.json"`
- **THEN** extract bucket as `"crawl-results"` and path as `"tiktok/proj_xyz/brand/batch_000.json"`

#### Scenario: Handle path with no bucket separator

- **WHEN** `minio_path` contains no forward slash
- **THEN** treat entire string as path with empty bucket and log warning

#### Scenario: Handle empty minio_path

- **WHEN** `minio_path` is empty or null
- **THEN** raise ValueError and nack message

---

### Requirement: Event Metadata Extraction

The system SHALL extract event correlation metadata for logging and tracing.

#### Scenario: Extract correlation fields

- **WHEN** processing a `data.collected` event
- **THEN** extract `event_id` and `timestamp` for log correlation

#### Scenario: Log event context

- **WHEN** processing batch items
- **THEN** include `event_id`, `project_id`, `job_id`, `batch_index` in all log entries

---

### Requirement: Dual-Mode Message Format Detection

The system SHALL support both new event format and legacy message format during migration.

#### Scenario: Detect new event format

- **WHEN** message envelope contains `payload.minio_path` field
- **THEN** process using new event format handler

#### Scenario: Detect legacy format

- **WHEN** message envelope contains `data_ref.bucket` and `data_ref.path` fields
- **THEN** process using legacy format handler

#### Scenario: Detect inline format

- **WHEN** message envelope contains direct post data (no `payload` or `data_ref`)
- **THEN** process using inline format handler

#### Scenario: Handle ambiguous format

- **WHEN** message envelope matches multiple format patterns
- **THEN** prefer new event format over legacy

