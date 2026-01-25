## ADDED Requirements

### Requirement: Brand Name Event Field Extraction

The system SHALL extract brand_name from data.collected event payload for brand-level filtering.

#### Scenario: Extract brand_name from payload

- **WHEN** a `data.collected` event is received
- **THEN** extract `brand_name` from `payload.brand_name`
- **AND** include in event metadata dictionary

#### Scenario: Log missing brand_name

- **WHEN** event payload does not contain `brand_name` field
- **THEN** log WARNING with event_id indicating missing brand_name
- **AND** add `brand_name` to missing_fields list

#### Scenario: Include brand_name in debug logging

- **WHEN** logging extracted event metadata at DEBUG level
- **THEN** include `brand_name` value in log output

## MODIFIED Requirements

### Requirement: Data Collected Event Parsing

The system SHALL consume `data.collected` events from the `smap.events` RabbitMQ exchange with routing key `data.collected`.

#### Scenario: Parse valid event

- **WHEN** a `data.collected` event is received with all required fields
- **THEN** extract `event_id`, `timestamp`, and payload fields (`project_id`, `job_id`, `platform`, `minio_path`, `content_count`, `batch_index`, `brand_name`, `keyword`, `task_type`)

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

### Requirement: Event Metadata Extraction

The system SHALL extract event correlation metadata for logging and tracing.

#### Scenario: Extract correlation fields

- **WHEN** processing a `data.collected` event
- **THEN** extract `event_id` and `timestamp` for log correlation

#### Scenario: Extract brand and keyword fields

- **WHEN** processing a `data.collected` event
- **THEN** extract `brand_name` from `payload.brand_name`
- **AND** extract `keyword` from `payload.keyword`

#### Scenario: Log event context

- **WHEN** processing batch items
- **THEN** include `event_id`, `project_id`, `job_id`, `batch_index`, `brand_name`, `keyword` in all log entries

---

### Requirement: Data Extraction Debug Logging

The system SHALL provide detailed logging for data extraction from crawler events to aid debugging.

#### Scenario: Log event metadata on receive

- **WHEN** a crawler event is received
- **THEN** log event_id, job_id, platform, batch_index, brand_name at INFO level

#### Scenario: Log extracted fields before processing

- **WHEN** extracting metadata from event payload
- **THEN** log all extracted fields (job_id, batch_index, task_type, keyword_source, brand_name, keyword, crawled_at) at DEBUG level

#### Scenario: Log missing fields

- **WHEN** expected metadata fields are missing from event payload
- **THEN** log a WARNING with the list of missing fields (including brand_name if missing)
