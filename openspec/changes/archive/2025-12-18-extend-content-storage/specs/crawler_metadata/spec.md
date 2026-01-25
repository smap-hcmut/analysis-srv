## ADDED Requirements

### Requirement: Brand Name Extraction

The system SHALL extract brand name from event payload for brand-level filtering and analysis.

#### Scenario: Extract brand_name from event payload

- **WHEN** processing `data.collected` event
- **THEN** extract `brand_name` from `payload.brand_name`
- **AND** include in event metadata dictionary

#### Scenario: Log missing brand_name

- **WHEN** event payload does not contain `brand_name`
- **THEN** log WARNING with event_id indicating missing brand_name
- **AND** continue processing with NULL brand_name

#### Scenario: Enrich item with brand_name

- **WHEN** enriching item with batch context
- **THEN** add `brand_name` to item meta from event metadata

---

### Requirement: Content Fields Enrichment

The system SHALL enrich analytics results with content fields from crawler items.

#### Scenario: Enrich with content text

- **WHEN** enriching item with batch context
- **THEN** add `content_text` from `item.content.text`

#### Scenario: Enrich with transcription

- **WHEN** enriching item with batch context
- **THEN** add `content_transcription` from `item.content.transcription`

#### Scenario: Enrich with media duration

- **WHEN** enriching item with batch context
- **THEN** add `media_duration` from `item.content.duration`

#### Scenario: Enrich with hashtags

- **WHEN** enriching item with batch context
- **THEN** add `hashtags` from `item.content.hashtags` as array

#### Scenario: Enrich with permalink

- **WHEN** enriching item with batch context
- **THEN** add `permalink` from `item.meta.permalink`

---

### Requirement: Author Fields Enrichment

The system SHALL enrich analytics results with author fields from crawler items.

#### Scenario: Enrich with author ID

- **WHEN** enriching item with batch context
- **THEN** add `author_id` from `item.author.id`

#### Scenario: Enrich with author name

- **WHEN** enriching item with batch context
- **THEN** add `author_name` from `item.author.name`

#### Scenario: Enrich with author username

- **WHEN** enriching item with batch context
- **THEN** add `author_username` from `item.author.username`

#### Scenario: Enrich with author avatar URL

- **WHEN** enriching item with batch context
- **THEN** add `author_avatar_url` from `item.author.avatar_url`

#### Scenario: Enrich with author verified status

- **WHEN** enriching item with batch context
- **THEN** add `author_is_verified` from `item.author.is_verified`
- **AND** default to FALSE if not present

---

### Requirement: Extended Crawler Metadata Fields

The system SHALL include new fields in crawler metadata extraction for persistence.

#### Scenario: Include brand_name in crawler fields

- **WHEN** extracting crawler metadata for persistence
- **THEN** include `brand_name` in extracted fields

#### Scenario: Include keyword in crawler fields

- **WHEN** extracting crawler metadata for persistence
- **THEN** include `keyword` in extracted fields

#### Scenario: Include content fields in crawler metadata

- **WHEN** extracting crawler metadata for persistence
- **THEN** include `content_text`, `content_transcription`, `media_duration`, `hashtags`, `permalink`

#### Scenario: Include author fields in crawler metadata

- **WHEN** extracting crawler metadata for persistence
- **THEN** include `author_id`, `author_name`, `author_username`, `author_avatar_url`, `author_is_verified`

## MODIFIED Requirements

### Requirement: Metadata Enrichment

The system SHALL enrich analytics results with crawler metadata before saving.

#### Scenario: Enrich with all metadata fields

- **WHEN** analytics pipeline completes for success item
- **THEN** add `job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version` to result dictionary
- **AND** add `brand_name`, `keyword` from event payload
- **AND** add `content_text`, `content_transcription`, `media_duration`, `hashtags`, `permalink` from item content
- **AND** add `author_id`, `author_name`, `author_username`, `author_avatar_url`, `author_is_verified` from item author

#### Scenario: Handle missing metadata fields

- **WHEN** item meta is missing optional fields (e.g., `keyword_source`, `brand_name`, `author_avatar_url`)
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
- **AND** extract `brand_name` from `payload.brand_name`
- **AND** extract `keyword` from `payload.keyword`
