# Capability: Error Handling

## ADDED Requirements

### Requirement: Error Code Constants

The system SHALL define 17 structured error codes categorized into 7 types.

#### Scenario: Define rate limiting errors

- **WHEN** defining error code constants
- **THEN** include `RATE_LIMITED`, `AUTH_FAILED`, `ACCESS_DENIED` in category `rate_limiting`

#### Scenario: Define content errors

- **WHEN** defining error code constants
- **THEN** include `CONTENT_REMOVED`, `CONTENT_NOT_FOUND`, `CONTENT_UNAVAILABLE` in category `content`

#### Scenario: Define network errors

- **WHEN** defining error code constants
- **THEN** include `NETWORK_ERROR`, `TIMEOUT`, `CONNECTION_REFUSED`, `DNS_ERROR` in category `network`

#### Scenario: Define all error categories

- **WHEN** defining error code taxonomy
- **THEN** include categories: `rate_limiting`, `content`, `network`, `parsing`, `media`, `storage`, `generic`

---

### Requirement: Error Code Categorization

The system SHALL categorize error codes into high-level categories for analytics.

#### Scenario: Categorize rate limiting error

- **WHEN** error code is `RATE_LIMITED`
- **THEN** return category `rate_limiting`

#### Scenario: Categorize content error

- **WHEN** error code is `CONTENT_REMOVED`
- **THEN** return category `content`

#### Scenario: Categorize unknown error

- **WHEN** error code is not in known list
- **THEN** return category `generic` as fallback

---

### Requirement: Error Item Detection

The system SHALL detect and handle items with `fetch_status: "error"` without failing batch processing.

#### Scenario: Detect error item

- **WHEN** item `meta.fetch_status` is `"error"`
- **THEN** skip analytics pipeline and route to error handling path

#### Scenario: Extract error metadata

- **WHEN** processing error item
- **THEN** extract `error_code`, `fetch_error` message, and `error_details` JSONB from item meta

#### Scenario: Handle missing error fields

- **WHEN** error item is missing `error_code` or `fetch_error`
- **THEN** use defaults (`error_code="UNKNOWN_ERROR"`, `fetch_error="Unknown error"`)

---

### Requirement: Error Record Storage

The system SHALL store error records in dedicated `crawl_errors` table for analytics.

#### Scenario: Save error record

- **WHEN** processing error item
- **THEN** insert record into `crawl_errors` with `content_id`, `project_id`, `job_id`, `platform`, `error_code`, `error_category`, `error_message`, `error_details`, `permalink`

#### Scenario: Handle dry-run error

- **WHEN** processing error item with `project_id=None` (dry-run)
- **THEN** save error record with `project_id` as NULL

#### Scenario: Store error timestamp

- **WHEN** saving error record
- **THEN** set `created_at` to current timestamp (database default)

---

### Requirement: Error Analytics Fields in Main Table

The system SHALL add error tracking fields to `post_analytics` table for filtering.

#### Scenario: Mark success item

- **WHEN** saving success item analytics
- **THEN** set `fetch_status="success"`, `fetch_error=NULL`, `error_code=NULL`

#### Scenario: Mark error item

- **WHEN** saving error item placeholder (optional)
- **THEN** set `fetch_status="error"`, populate `fetch_error` and `error_code`

---

### Requirement: Error Logging

The system SHALL log error items with structured context for debugging.

#### Scenario: Log error item warning

- **WHEN** processing error item
- **THEN** log at WARNING level with `content_id`, `error_code`, `error_category`, `error_message`

#### Scenario: Include batch context in error logs

- **WHEN** logging error item
- **THEN** include `event_id`, `job_id`, `batch_index` in log entry

---

### Requirement: Error Distribution Tracking

The system SHALL track error distribution for monitoring and alerting.

#### Scenario: Aggregate errors by code

- **WHEN** batch processing completes
- **THEN** return dictionary mapping `error_code` to count

#### Scenario: Track errors by category

- **WHEN** emitting metrics
- **THEN** aggregate error counts by `error_category`

#### Scenario: Calculate error rate

- **WHEN** batch processing completes
- **THEN** calculate error rate as `error_count / (success_count + error_count) * 100`
