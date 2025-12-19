## ADDED Requirements

### Requirement: Content Storage Fields

The system SHALL store content data from crawler items for UI display and analysis.

#### Scenario: Store content text

- **WHEN** saving analytics result for success item
- **THEN** populate `content_text` field from `item.content.text`

#### Scenario: Store transcription

- **WHEN** saving analytics result with transcription available
- **THEN** populate `content_transcription` field from `item.content.transcription`

#### Scenario: Store media duration

- **WHEN** saving analytics result for video content
- **THEN** populate `media_duration` field from `item.content.duration` (in seconds)

#### Scenario: Store hashtags

- **WHEN** saving analytics result with hashtags
- **THEN** populate `hashtags` field as JSONB array from `item.content.hashtags`

#### Scenario: Store permalink

- **WHEN** saving analytics result
- **THEN** populate `permalink` field from `item.meta.permalink`

---

### Requirement: Author Information Storage

The system SHALL store author information from crawler items for KOL analysis and display.

#### Scenario: Store author ID

- **WHEN** saving analytics result
- **THEN** populate `author_id` field from `item.author.id`

#### Scenario: Store author name

- **WHEN** saving analytics result
- **THEN** populate `author_name` field from `item.author.name`

#### Scenario: Store author username

- **WHEN** saving analytics result
- **THEN** populate `author_username` field from `item.author.username`

#### Scenario: Store author avatar URL

- **WHEN** saving analytics result with avatar available
- **THEN** populate `author_avatar_url` field from `item.author.avatar_url`

#### Scenario: Store author verified status

- **WHEN** saving analytics result
- **THEN** populate `author_is_verified` field from `item.author.is_verified` (default FALSE)

---

### Requirement: Brand and Keyword Storage

The system SHALL store brand and keyword context from event payload for filtering and analysis.

#### Scenario: Store brand name

- **WHEN** saving analytics result
- **THEN** populate `brand_name` field from `event.payload.brand_name`

#### Scenario: Store keyword

- **WHEN** saving analytics result
- **THEN** populate `keyword` field from `event.payload.keyword`

#### Scenario: Handle missing brand name

- **WHEN** event payload does not contain `brand_name`
- **THEN** set `brand_name` to NULL
- **AND** log WARNING about missing brand_name

---

### Requirement: Post Comments Table

The system SHALL store comments in a separate table for comment-level analysis.

#### Scenario: Create post_comments table

- **WHEN** running database migration
- **THEN** create table `post_comments` with columns:
  - `id SERIAL PRIMARY KEY`
  - `post_id VARCHAR(50) NOT NULL` (FK to post_analytics)
  - `comment_id VARCHAR(100)`
  - `text TEXT NOT NULL`
  - `author_name VARCHAR(200)`
  - `likes INTEGER DEFAULT 0`
  - `sentiment VARCHAR(10)`
  - `sentiment_score FLOAT`
  - `commented_at TIMESTAMP`
  - `created_at TIMESTAMP DEFAULT NOW()`

#### Scenario: Save comment from crawler item

- **WHEN** processing item with comments array
- **THEN** save each comment to `post_comments` table
- **AND** link to parent post via `post_id` foreign key

#### Scenario: Extract comment author name

- **WHEN** comment has nested `user.name` structure
- **THEN** extract `author_name` from `comment.user.name`
- **WHEN** comment has flat `author_name` field
- **THEN** use `comment.author_name` directly

#### Scenario: Handle comment timestamp

- **WHEN** comment has `created_at` field
- **THEN** parse ISO 8601 timestamp and store in `commented_at`

---

### Requirement: Content Storage Indexes

The system SHALL create indexes for efficient querying of new fields.

#### Scenario: Create brand_name index

- **WHEN** running database migration
- **THEN** create index `idx_post_analytics_brand_name` on `brand_name` column

#### Scenario: Create keyword index

- **WHEN** running database migration
- **THEN** create index `idx_post_analytics_keyword` on `keyword` column

#### Scenario: Create author_id index

- **WHEN** running database migration
- **THEN** create index `idx_post_analytics_author_id` on `author_id` column

#### Scenario: Create post_comments indexes

- **WHEN** running database migration
- **THEN** create index `idx_post_comments_post_id` on `post_id` column
- **AND** create index `idx_post_comments_sentiment` on `sentiment` column
- **AND** create index `idx_post_comments_commented_at` on `commented_at` column
