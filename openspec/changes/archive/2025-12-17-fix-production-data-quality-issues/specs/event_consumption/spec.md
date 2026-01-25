# event_consumption Specification Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
