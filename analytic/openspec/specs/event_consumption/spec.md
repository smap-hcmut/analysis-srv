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

#### Scenario: Log raw event payload for debugging

- **WHEN** a `data.collected` event is received
- **THEN** log the raw event payload structure at DEBUG level for troubleshooting

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

### Requirement: Project ID UUID Validation

The system SHALL validate and sanitize `project_id` field to ensure it contains a valid UUID before database operations.

#### Scenario: Valid UUID passes through

- **WHEN** `project_id` is a valid UUID format (e.g., `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`)
- **THEN** use the value as-is without modification

#### Scenario: Extract UUID from invalid format

- **WHEN** `project_id` contains a valid UUID with extra suffix (e.g., `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor"`)
- **THEN** extract the valid UUID portion (`"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`)
- **AND** log a warning with original and sanitized values

#### Scenario: Reject completely invalid project_id

- **WHEN** `project_id` does not contain any valid UUID pattern (e.g., `"invalid-string"`)
- **THEN** raise ValueError with descriptive message

#### Scenario: Handle empty project_id

- **WHEN** `project_id` is empty string or None
- **THEN** raise ValueError indicating project_id is required

---

### Requirement: UUID Utility Functions

The system SHALL provide utility functions for UUID validation and extraction in `utils/uuid_utils.py`.

#### Scenario: Extract UUID from string

- **WHEN** calling `extract_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")`
- **THEN** return `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`

#### Scenario: Extract UUID returns None for invalid

- **WHEN** calling `extract_uuid("invalid-string")`
- **THEN** return `None`

#### Scenario: Validate UUID format

- **WHEN** calling `is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80")`
- **THEN** return `True`

#### Scenario: Validate UUID rejects invalid

- **WHEN** calling `is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")`
- **THEN** return `False`

### Requirement: BigInt ID Serialization

The system SHALL serialize post IDs as strings to prevent JavaScript precision loss for IDs exceeding `Number.MAX_SAFE_INTEGER` (9007199254740991).

#### Scenario: Serialize TikTok ID as string

- **WHEN** processing a TikTok post with ID `7576276451171880962` (19 digits)
- **THEN** serialize the ID as string `"7576276451171880962"` in JSON output

#### Scenario: Detect truncated ID

- **WHEN** an ID ends with multiple zeros (e.g., `7576276451171880000`)
- **THEN** log a warning indicating potential precision loss

#### Scenario: Validate ID format

- **WHEN** processing a post ID
- **THEN** validate it matches expected platform ID format before processing

---

### Requirement: Data Extraction Debug Logging

The system SHALL provide detailed logging for data extraction from crawler events to aid debugging.

#### Scenario: Log event metadata on receive

- **WHEN** a crawler event is received
- **THEN** log event_id, job_id, platform, batch_index at INFO level

#### Scenario: Log extracted fields before processing

- **WHEN** extracting metadata from event payload
- **THEN** log all extracted fields (job_id, batch_index, task_type, keyword_source, crawled_at) at DEBUG level

#### Scenario: Log missing fields

- **WHEN** expected metadata fields are missing from event payload
- **THEN** log a WARNING with the list of missing fields

