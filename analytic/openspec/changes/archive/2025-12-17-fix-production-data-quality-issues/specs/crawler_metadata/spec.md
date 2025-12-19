# crawler_metadata Specification Delta

## MODIFIED Requirements

### Requirement: Metadata Enrichment

The system SHALL enrich analytics results with crawler metadata before saving.

#### Scenario: Enrich with all metadata fields

- **WHEN** analytics pipeline completes for success item
- **THEN** add `job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version` to result dictionary

#### Scenario: Handle missing metadata fields

- **WHEN** item meta is missing optional fields (e.g., `keyword_source`)
- **THEN** set field to NULL in database (not string "NULL")

#### Scenario: Preserve existing project_id

- **WHEN** analytics result already has `project_id` from extraction
- **THEN** keep extracted value (do not overwrite with event payload value)

#### Scenario: Extract metadata from correct payload location

- **WHEN** processing crawler event
- **THEN** extract `job_id` from `payload.job_id` or `meta.job_id`
- **AND** extract `batch_index` from `payload.batch_index` or `meta.batch_index`
- **AND** extract `task_type` from `payload.task_type` or item `meta.task_type`
- **AND** extract `keyword_source` from `payload.keyword` or item `meta.keyword_source`

---

## ADDED Requirements

### Requirement: NULL Value Serialization

The system SHALL serialize NULL values correctly as JSON null, not as string "NULL".

#### Scenario: Serialize None as null

- **WHEN** a field value is Python `None`
- **THEN** serialize as JSON `null` in output

#### Scenario: Sanitize string NULL values

- **WHEN** a field contains string value `"NULL"` or `"null"`
- **THEN** convert to Python `None` before saving to database

#### Scenario: Handle empty strings

- **WHEN** a field contains empty string `""`
- **THEN** preserve as empty string (do not convert to NULL)

---

### Requirement: Boolean Value Serialization

The system SHALL serialize boolean values correctly as JSON true/false, not as strings.

#### Scenario: Serialize True as true

- **WHEN** a boolean field value is Python `True`
- **THEN** serialize as JSON `true` in output

#### Scenario: Serialize False as false

- **WHEN** a boolean field value is Python `False`
- **THEN** serialize as JSON `false` in output

#### Scenario: Parse string boolean values

- **WHEN** a boolean field contains string `"True"` or `"true"`
- **THEN** convert to Python `True` before saving
- **WHEN** a boolean field contains string `"False"` or `"false"`
- **THEN** convert to Python `False` before saving

---

### Requirement: Data Quality Validation

The system SHALL validate data quality before persisting to database.

#### Scenario: Validate required fields present

- **WHEN** saving analytics result
- **THEN** verify `id`, `platform`, `published_at` are present and valid

#### Scenario: Log data quality warnings

- **WHEN** optional metadata fields are missing
- **THEN** log WARNING with list of missing fields for debugging

#### Scenario: Track metadata completeness

- **WHEN** batch processing completes
- **THEN** log statistics on metadata completeness (% of records with full metadata)
