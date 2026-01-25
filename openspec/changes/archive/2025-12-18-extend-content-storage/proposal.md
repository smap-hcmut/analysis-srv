# Change: Extend Content Storage for Contract v2.0

## Why

Analytics Service cần lưu đầy đủ dữ liệu từ Crawler theo Contract v2.0 để:

- Hiển thị nội dung bài viết (text, transcription) trên UI
- Filter/query theo brand, keyword
- Hiển thị thông tin author (name, username, avatar, verified)
- Lưu và phân tích comments riêng
- Hỗ trợ các business queries: brand monitoring, competitor analysis, crisis detection

Hiện tại, nhiều fields quan trọng từ Crawler không được lưu vào database, chỉ được dùng để phân tích rồi bỏ.

## What Changes

### Database Schema

1. **Add columns to `post_analytics`:**

   - Content: `content_text`, `content_transcription`, `media_duration`, `hashtags`, `permalink`
   - Author: `author_id`, `author_name`, `author_username`, `author_avatar_url`, `author_is_verified`
   - Brand/Keyword: `brand_name`, `keyword`

2. **Create new table `post_comments`:**

   - Store comments separately with FK to `post_analytics`
   - Support comment-level sentiment analysis

3. **Add indexes:**
   - `idx_post_analytics_brand_name`
   - `idx_post_analytics_keyword`
   - `idx_post_analytics_author_id`
   - `idx_post_comments_post_id`
   - `idx_post_comments_sentiment`

### Code Changes

1. **Consumer (`internal/consumers/main.py`):**

   - Extract `brand_name` from event payload
   - Enrich items with content, author, brand/keyword fields
   - Process and save comments to new table

2. **Orchestrator (`services/analytics/orchestrator.py`):**

   - Add new fields to `_extract_crawler_metadata()`

3. **Repository:**

   - Create `CommentRepository` for comment operations

4. **Models (`models/database.py`):**
   - Add new columns to `PostAnalytics`
   - Add new `PostComment` model

## Impact

- **Affected specs:**

  - `storage` - Add new columns and table
  - `crawler_metadata` - Add brand_name, keyword extraction
  - `event_consumption` - Extract brand_name from event

- **Affected code:**

  - `models/database.py`
  - `internal/consumers/main.py`
  - `services/analytics/orchestrator.py`
  - `repository/` (new file)
  - `migrations/versions/` (new migration)

- **No breaking changes:**
  - All new columns are nullable
  - Existing data remains valid
  - Backward compatible with events without new fields

## References

- `document/crawler-analyst-data-contract.md` - Contract v2.0 specification
- `document/brand-keyword-implementation-plan.md` - Implementation details
- `document/analytics-erd.md` - ERD diagrams
- `document/analytics-query-capabilities.md` - Query capabilities
