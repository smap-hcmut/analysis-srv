# result_publishing Specification

## Purpose
TBD - created by archiving change add-result-publisher. Update Purpose after archive.
## Requirements
### Requirement: Result Message Format

The system SHALL format analyze results as JSON messages following the integration contract schema.

#### Scenario: Format successful batch result

- **WHEN** batch processing completes with 48 successes and 2 errors out of 50 items
- **THEN** create message with `success: true`, `batch_size: 50`, `success_count: 48`, `error_count: 2`

#### Scenario: Format failed batch result

- **WHEN** batch processing fails completely (e.g., MinIO fetch error)
- **THEN** create message with `success: false`, `success_count: 0`, `error_count: batch_size`

#### Scenario: Include task type identifier

- **WHEN** creating any analyze result message
- **THEN** set `task_type` field to `"analyze_result"` for Collector routing

#### Scenario: Include project context

- **WHEN** creating analyze result message
- **THEN** include `project_id` and `job_id` from original event for correlation

---

### Requirement: Result Publishing

The system SHALL publish analyze result messages to RabbitMQ exchange `results.inbound` with routing key `analyze.result`.

#### Scenario: Publish to correct exchange

- **WHEN** batch processing completes
- **THEN** publish message to exchange `results.inbound` with routing key `analyze.result`

#### Scenario: Use persistent delivery mode

- **WHEN** publishing analyze result message
- **THEN** set delivery mode to persistent (2) to survive broker restarts

#### Scenario: Publish one message per batch

- **WHEN** batch contains 50 items
- **THEN** publish exactly 1 aggregated result message (not 50 individual messages)

---

### Requirement: Publisher Configuration

The system SHALL support configurable exchange and routing key for result publishing.

#### Scenario: Configure publish exchange

- **WHEN** environment variable `PUBLISH_EXCHANGE` is set to `"custom.exchange"`
- **THEN** publish results to `"custom.exchange"` instead of default `"results.inbound"`

#### Scenario: Configure routing key

- **WHEN** environment variable `PUBLISH_ROUTING_KEY` is set to `"custom.routing"`
- **THEN** publish results with routing key `"custom.routing"` instead of default `"analyze.result"`

#### Scenario: Feature flag for publishing

- **WHEN** environment variable `PUBLISH_ENABLED` is set to `"false"`
- **THEN** skip result publishing (for gradual rollout)

---

### Requirement: Publisher Lifecycle

The system SHALL manage publisher lifecycle alongside consumer lifecycle.

#### Scenario: Initialize publisher on startup

- **WHEN** consumer service starts
- **THEN** create publisher instance and declare exchange before consuming messages

#### Scenario: Share connection with consumer

- **WHEN** initializing publisher
- **THEN** reuse existing RabbitMQ connection from consumer (create new channel)

#### Scenario: Cleanup on shutdown

- **WHEN** consumer service shuts down
- **THEN** close publisher channel gracefully before closing connection

---

### Requirement: Batch Result Aggregation

The system SHALL aggregate individual item results into a single batch result message.

#### Scenario: Aggregate success items

- **WHEN** batch contains items with successful analytics processing
- **THEN** include summary in `results` array with `content_id`, `sentiment`, `sentiment_score`

#### Scenario: Aggregate error items

- **WHEN** batch contains items with failed processing
- **THEN** include summary in `errors` array with `content_id` and `error` message

#### Scenario: Calculate success flag

- **WHEN** aggregating batch results
- **THEN** set `success: true` if `error_count < batch_size` (majority succeeded)

---

### Requirement: Error Result Publishing

The system SHALL publish error results when batch processing fails at infrastructure level.

#### Scenario: MinIO fetch failure

- **WHEN** MinIO fetch fails for entire batch
- **THEN** publish error result with `success: false`, `error_count: item_count`, and batch-level error in `errors` array

#### Scenario: Batch-level error format

- **WHEN** publishing batch-level error
- **THEN** use `content_id: "batch"` and include error message in `error` field

---

### Requirement: Publish Failure Handling

The system SHALL handle publish failures gracefully without blocking message consumption.

#### Scenario: Log publish failure

- **WHEN** publishing to RabbitMQ fails
- **THEN** log error with message details and continue processing

#### Scenario: Do not retry on failure

- **WHEN** publishing fails
- **THEN** do not retry (rely on Collector timeout detection for missing results)

#### Scenario: Do not block consumer

- **WHEN** publishing fails
- **THEN** acknowledge original message and continue consuming next message

