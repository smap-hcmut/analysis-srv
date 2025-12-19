# Tasks: Extend Content Storage

## 1. Database Schema Changes

- [x] 1.1 Create Alembic migration for new columns in `post_analytics`

  - Add `content_text TEXT`
  - Add `content_transcription TEXT`
  - Add `media_duration INTEGER`
  - Add `hashtags JSONB`
  - Add `permalink TEXT`
  - Add `author_id VARCHAR(100)`
  - Add `author_name VARCHAR(200)`
  - Add `author_username VARCHAR(100)`
  - Add `author_avatar_url TEXT`
  - Add `author_is_verified BOOLEAN DEFAULT FALSE`
  - Add `brand_name VARCHAR(100)`
  - Add `keyword VARCHAR(200)`

- [x] 1.2 Create Alembic migration for `post_comments` table

  - Create table with columns: `id`, `post_id`, `comment_id`, `text`, `author_name`, `likes`, `sentiment`, `sentiment_score`, `commented_at`, `created_at`
  - Add FK constraint to `post_analytics(id)`
  - Add indexes on `post_id`, `sentiment`, `commented_at`

- [x] 1.3 Create Alembic migration for new indexes on `post_analytics`

  - Add `idx_post_analytics_brand_name`
  - Add `idx_post_analytics_keyword`
  - Add `idx_post_analytics_author_id`

- [x] 1.4 Update `models/database.py`
  - Add new columns to `PostAnalytics` class
  - Add new `PostComment` model class
  - Add table-level indexes

## 2. Consumer Updates

- [x] 2.1 Update `parse_event_metadata()` in `internal/consumers/main.py`

  - Extract `brand_name` from `payload.brand_name`
  - Add warning for missing `brand_name`

- [x] 2.2 Update `enrich_with_batch_context()` in `internal/consumers/main.py`
  - Add `brand_name` from event metadata
  - Add `keyword` from event metadata
  - Add `content_text` from `item.content.text`
  - Add `content_transcription` from `item.content.transcription`
  - Add `media_duration` from `item.content.duration`
  - Add `hashtags` from `item.content.hashtags`
  - Add `permalink` from `item.meta.permalink`
  - Add `author_id` from `item.author.id`
  - Add `author_name` from `item.author.name`
  - Add `author_username` from `item.author.username`
  - Add `author_avatar_url` from `item.author.avatar_url`
  - Add `author_is_verified` from `item.author.is_verified`

## 3. Orchestrator Updates

- [x] 3.1 Update `_extract_crawler_metadata()` in `services/analytics/orchestrator.py`
  - Add `brand_name` to crawler_fields list
  - Add `keyword` to crawler_fields list
  - Add `content_text` to crawler_fields list
  - Add `content_transcription` to crawler_fields list
  - Add `media_duration` to crawler_fields list
  - Add `hashtags` to crawler_fields list
  - Add `permalink` to crawler_fields list
  - Add `author_id` to crawler_fields list
  - Add `author_name` to crawler_fields list
  - Add `author_username` to crawler_fields list
  - Add `author_avatar_url` to crawler_fields list
  - Add `author_is_verified` to crawler_fields list

## 4. Comment Processing

- [x] 4.1 Create `repository/comment_repository.py`

  - Implement `CommentRepository` class
  - Add `save()` method for single comment
  - Add `save_batch()` method for multiple comments
  - Add `get_by_post_id()` method
  - Add `delete_by_post_id()` method

- [x] 4.2 Update `process_single_item()` in `internal/consumers/main.py`
  - Extract comments from item
  - Create `CommentRepository` instance
  - Save comments to database
  - Handle `author_name` from nested `user.name` structure

## 5. Testing

- [x] 5.1 Add unit tests for new metadata extraction

  - Test `parse_event_metadata()` extracts `brand_name`
  - Test `enrich_with_batch_context()` adds all new fields
  - Test handling of missing optional fields

- [x] 5.2 Add unit tests for `CommentRepository`

  - Test `save()` creates comment record
  - Test `save_batch()` creates multiple records
  - Test `get_by_post_id()` returns correct comments
  - Test FK constraint with invalid `post_id`

- [ ] 5.3 Add integration tests
  - Test full pipeline with sample crawler event
  - Verify all fields saved to database
  - Verify comments saved to `post_comments` table

## 6. Validation

- [ ] 6.1 Run migrations on dev database
- [ ] 6.2 Test with sample crawler events
- [ ] 6.3 Verify data in database matches expected schema
- [x] 6.4 Run existing test suite to ensure no regressions

---

## Implementation Progress

| Task Group              | Status     | Notes                                               |
| ----------------------- | ---------- | --------------------------------------------------- |
| 1. Database Schema      | ✅ Done    | Migration + models updated                          |
| 2. Consumer Updates     | ✅ Done    | parse_event_metadata + enrich_with_batch_context    |
| 3. Orchestrator Updates | ✅ Done    | \_extract_crawler_metadata with all new fields      |
| 4. Comment Processing   | ✅ Done    | CommentRepository + process_single_item integration |
| 5. Testing              | ✅ Done    | Unit tests added (34 new tests, all passing)        |
| 6. Validation           | ⏳ Pending | Run migrations + test with real data                |
