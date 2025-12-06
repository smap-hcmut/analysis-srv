# crawler_metadata Specification

## Purpose
TBD - created by archiving change integrate-crawler-events. Update Purpose after archive.
## Requirements
### Requirement: Batch Context Fields

The system SHALL store batch context metadata for job tracking and correlation.

#### Scenario: Store job identifier

- **WHEN** saving analytics result
- **THEN** populate `job_id` field from event payload (e.g., `"proj_xyz-brand-0"`)

#### Scenario: Store batch index

- **WHEN** saving analytics result
- **THEN** populate `batch_index` field from event payload (e.g., `1`, `2`, `3`)

#### Scenario: Store task type

- **WHEN** saving analytics result
- **THEN** populate `task_type` field from item meta (e.g., `"research_and_crawl"`, `"dryrun_keyword"`)

---

### Requirement: Crawler Source Metadata

The system SHALL store crawler-specific metadata for audit and debugging.

#### Scenario: Store keyword source

- **WHEN** saving analytics result
- **THEN** populate `keyword_source` field from item meta (e.g., `"VinFast VF8"`)

#### Scenario: Store crawl timestamp

- **WHEN** saving analytics result
- **THEN** populate `crawled_at` field from item meta ISO 8601 timestamp

#### Scenario: Store pipeline version

- **WHEN** saving analytics result
- **THEN** populate `pipeline_version` field from item meta (e.g., `"crawler_tiktok_v3"`)

---

### Requirement: Database Schema Extensions

The system SHALL add crawler metadata columns to `post_analytics` table.

#### Scenario: Add batch context columns

- **WHEN** running database migration
- **THEN** add columns `job_id VARCHAR(100)`, `batch_index INTEGER`, `task_type VARCHAR(30)`

#### Scenario: Add crawler metadata columns

- **WHEN** running database migration
- **THEN** add columns `keyword_source VARCHAR(200)`, `crawled_at TIMESTAMP`, `pipeline_version VARCHAR(50)`

#### Scenario: Add error tracking columns

- **WHEN** running database migration
- **THEN** add columns `fetch_status VARCHAR(10)`, `fetch_error TEXT`, `error_code VARCHAR(50)`, `error_details JSONB`

#### Scenario: Create indexes for query performance

- **WHEN** running database migration
- **THEN** create indexes on `job_id`, `fetch_status`, `task_type`

---

### Requirement: CrawlError Table Schema

The system SHALL create dedicated `crawl_errors` table for error analytics.

#### Scenario: Define crawl_errors table structure

- **WHEN** running database migration
- **THEN** create table with columns: `id SERIAL`, `content_id VARCHAR(50)`, `project_id UUID`, `job_id VARCHAR(100)`, `platform VARCHAR(20)`, `error_code VARCHAR(50)`, `error_category VARCHAR(30)`, `error_message TEXT`, `error_details JSONB`, `permalink TEXT`, `created_at TIMESTAMP`

#### Scenario: Create error table indexes

- **WHEN** running database migration
- **THEN** create indexes on `project_id`, `error_code`, `created_at`

---

### Requirement: Metadata Enrichment

The system SHALL enrich analytics results with crawler metadata before saving.

#### Scenario: Enrich with all metadata fields

- **WHEN** analytics pipeline completes for success item
- **THEN** add `job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version` to result dictionary

#### Scenario: Handle missing metadata fields

- **WHEN** item meta is missing optional fields (e.g., `keyword_source`)
- **THEN** set field to NULL in database

#### Scenario: Preserve existing project_id

- **WHEN** analytics result already has `project_id` from extraction
- **THEN** keep extracted value (do not overwrite with event payload value)

