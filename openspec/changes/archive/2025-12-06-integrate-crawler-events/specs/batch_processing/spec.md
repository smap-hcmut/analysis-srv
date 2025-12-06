# Capability: Batch Processing

## ADDED Requirements

### Requirement: Batch Array Fetching

The system SHALL fetch batch arrays from MinIO containing 20-50 items per batch.

#### Scenario: Fetch TikTok batch

- **WHEN** fetching batch for platform `"tiktok"` from MinIO
- **THEN** expect array of up to 50 items and validate response is array type

#### Scenario: Fetch YouTube batch

- **WHEN** fetching batch for platform `"youtube"` from MinIO
- **THEN** expect array of up to 20 items and validate response is array type

#### Scenario: Handle non-array response

- **WHEN** MinIO returns non-array JSON (object or primitive)
- **THEN** raise ValueError with descriptive message and nack message

---

### Requirement: Batch Item Iteration

The system SHALL iterate through all items in a batch independently.

#### Scenario: Process all items in batch

- **WHEN** batch contains 50 items
- **THEN** process each item sequentially and track success/error counts

#### Scenario: Continue on item failure

- **WHEN** one item fails during processing
- **THEN** log error, increment error count, and continue processing remaining items

#### Scenario: Process partial batch

- **WHEN** batch contains fewer items than expected (e.g., 15 instead of 50)
- **THEN** process all available items and log batch size warning

---

### Requirement: Per-Item Processing

The system SHALL process each item with independent error handling and context enrichment.

#### Scenario: Process success item

- **WHEN** item has `fetch_status: "success"`
- **THEN** run analytics pipeline, enrich with batch context, and save to database

#### Scenario: Process error item

- **WHEN** item has `fetch_status: "error"`
- **THEN** skip analytics pipeline, store error record, and log warning

#### Scenario: Handle unknown fetch status

- **WHEN** item has unknown or missing `fetch_status`
- **THEN** log error, treat as error item, and continue batch processing

---

### Requirement: Batch Context Enrichment

The system SHALL enrich each processed item with batch context metadata.

#### Scenario: Enrich with project context

- **WHEN** processing item from batch
- **THEN** add `project_id` (extracted from `job_id`), `job_id`, `batch_index` to analytics result

#### Scenario: Enrich with crawler metadata

- **WHEN** processing success item
- **THEN** add `task_type`, `keyword_source`, `crawled_at`, `pipeline_version` from item meta

---

### Requirement: Batch Statistics Aggregation

The system SHALL aggregate and log batch processing statistics.

#### Scenario: Log batch completion

- **WHEN** all items in batch have been processed
- **THEN** log summary with `event_id`, `batch_index`, `success_count`, `error_count`, `processing_duration`

#### Scenario: Calculate success rate

- **WHEN** batch processing completes
- **THEN** calculate success rate as `success_count / (success_count + error_count) * 100`

#### Scenario: Track error distribution

- **WHEN** batch contains error items
- **THEN** aggregate error counts by `error_code` for metrics reporting

---

### Requirement: Batch Size Validation

The system SHALL validate batch sizes against platform expectations and log warnings for deviations.

#### Scenario: Validate TikTok batch size

- **WHEN** processing TikTok batch with unexpected size (not 50)
- **THEN** log warning with expected vs actual size but continue processing

#### Scenario: Validate YouTube batch size

- **WHEN** processing YouTube batch with unexpected size (not 20)
- **THEN** log warning with expected vs actual size but continue processing

#### Scenario: Accept partial batches

- **WHEN** batch size is smaller than expected (e.g., last batch of job)
- **THEN** process normally and log informational message

---

### Requirement: Project ID Extraction

The system SHALL extract `project_id` from `job_id` using pattern matching.

#### Scenario: Extract from brand format

- **WHEN** `job_id` is `"proj_xyz789-brand-0"`
- **THEN** extract `project_id` as `"proj_xyz789"`

#### Scenario: Extract from competitor format

- **WHEN** `job_id` is `"proj_abc123-toyota-5"`
- **THEN** extract `project_id` as `"proj_abc123"`

#### Scenario: Detect dry-run task

- **WHEN** `job_id` matches UUID pattern (e.g., `"550e8400-e29b-41d4-a716-446655440000"`)
- **THEN** return `project_id` as `None` and set `is_dryrun` flag to `True`

#### Scenario: Handle complex project IDs

- **WHEN** `job_id` is `"my-complex-project-id-brand-0"`
- **THEN** extract `project_id` as `"my-complex-project-id"`

#### Scenario: Handle invalid format

- **WHEN** `job_id` does not match any known pattern
- **THEN** return `None` and log warning with original `job_id`
