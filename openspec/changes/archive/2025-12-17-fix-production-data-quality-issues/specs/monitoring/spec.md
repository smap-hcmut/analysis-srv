# monitoring Specification Delta

## ADDED Requirements

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
