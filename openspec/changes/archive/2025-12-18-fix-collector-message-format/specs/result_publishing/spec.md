## MODIFIED Requirements

### Requirement: Result Message Format

The system SHALL format analyze results as flat JSON messages following the Collector contract schema (`document/collector-crawler-contract.md` Section 3).

#### Scenario: Format successful batch result

- **WHEN** batch processing completes with 48 successes and 2 errors out of 50 items
- **THEN** create flat message with `project_id`, `job_id`, `task_type: "analyze_result"`, `batch_size: 50`, `success_count: 48`, `error_count: 2`

#### Scenario: Format failed batch result

- **WHEN** batch processing fails completely (e.g., MinIO fetch error)
- **THEN** create flat message with `success_count: 0`, `error_count: batch_size`

#### Scenario: Include task type identifier

- **WHEN** creating any analyze result message
- **THEN** set `task_type` field to `"analyze_result"` for Collector routing

#### Scenario: Include project context

- **WHEN** creating analyze result message
- **THEN** include `project_id` (required, non-empty) and `job_id` from original event for correlation

#### Scenario: Flat message structure

- **WHEN** serializing analyze result for Collector
- **THEN** output flat JSON with only 6 fields: `project_id`, `job_id`, `task_type`, `batch_size`, `success_count`, `error_count`
- **THEN** exclude internal fields like `results` and `errors` arrays from published message

#### Scenario: Reject empty project_id

- **WHEN** attempting to publish result with empty or null `project_id`
- **THEN** skip publishing and log error message
- **THEN** do not send malformed message to Collector

---

### Requirement: Result Publishing

The system SHALL publish analyze result messages to RabbitMQ exchange `results.inbound` with routing key `analyze.result`.

#### Scenario: Publish to correct exchange

- **WHEN** batch processing completes
- **THEN** publish flat message to exchange `results.inbound` with routing key `analyze.result`

#### Scenario: Use persistent delivery mode

- **WHEN** publishing analyze result message
- **THEN** set delivery mode to persistent (2) to survive broker restarts

#### Scenario: Publish one message per batch

- **WHEN** batch contains 50 items
- **THEN** publish exactly 1 aggregated result message (not 50 individual messages)

#### Scenario: Validate before publish

- **WHEN** publishing analyze result
- **THEN** validate `project_id` is non-empty before sending to RabbitMQ
