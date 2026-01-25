# Design: Extend Content Storage

## Context

Analytics Service hiện tại chỉ lưu kết quả phân tích (sentiment, impact, keywords) mà không lưu nội dung gốc từ Crawler. Contract v2.0 yêu cầu lưu thêm:

- Nội dung bài viết (text, transcription)
- Thông tin author đầy đủ
- Brand/keyword context
- Comments riêng biệt

## Goals / Non-Goals

### Goals

- Lưu đầy đủ content, author, brand/keyword vào `post_analytics`
- Tạo bảng `post_comments` để lưu comments riêng
- Hỗ trợ các business queries: brand monitoring, competitor analysis
- Backward compatible với data và events hiện tại

### Non-Goals

- Không tạo bảng riêng cho brands/keywords (đã có service khác quản lý)
- Không thay đổi logic phân tích sentiment/impact
- Không thay đổi message format từ Crawler

## Decisions

### Decision 1: Denormalized Storage

**What**: Lưu brand_name, keyword, author info trực tiếp vào `post_analytics` thay vì tạo bảng riêng.

**Why**:

- Single Source of Truth cho brands/keywords đã có ở Project Service
- Giảm complexity, không cần sync data
- Query performance tốt hơn (không cần JOIN)

**Alternatives considered**:

- Tạo `project_brands` và `brand_keywords` tables → Rejected vì duplicate data

### Decision 2: Separate Comments Table

**What**: Tạo bảng `post_comments` riêng thay vì lưu comments dạng JSONB trong `post_analytics`.

**Why**:

- Hỗ trợ comment-level sentiment analysis
- Query comments độc lập (top comments, negative comments)
- Scalable khi số lượng comments lớn

**Alternatives considered**:

- Lưu comments dạng JSONB array → Rejected vì khó query và analyze

### Decision 3: Nullable Columns

**What**: Tất cả columns mới đều nullable.

**Why**:

- Backward compatible với data hiện tại
- Handle gracefully khi Crawler chưa gửi đủ fields
- Không block processing nếu thiếu optional fields

## Data Flow

```
Crawler Event
    │
    ├── payload.brand_name ──────► post_analytics.brand_name
    ├── payload.keyword ─────────► post_analytics.keyword
    │
    └── MinIO Batch Item
            │
            ├── meta.permalink ──────► post_analytics.permalink
            │
            ├── content.text ────────► post_analytics.content_text
            ├── content.transcription► post_analytics.content_transcription
            ├── content.duration ────► post_analytics.media_duration
            ├── content.hashtags ────► post_analytics.hashtags (JSONB)
            │
            ├── author.id ───────────► post_analytics.author_id
            ├── author.name ─────────► post_analytics.author_name
            ├── author.username ─────► post_analytics.author_username
            ├── author.avatar_url ───► post_analytics.author_avatar_url
            ├── author.is_verified ──► post_analytics.author_is_verified
            │
            └── comments[] ──────────► post_comments (separate table)
```

## Schema Changes

### post_analytics (Extended)

```sql
-- NEW: Content fields
content_text TEXT,
content_transcription TEXT,
media_duration INTEGER,
hashtags JSONB,
permalink TEXT,

-- NEW: Author fields
author_id VARCHAR(100),
author_name VARCHAR(200),
author_username VARCHAR(100),
author_avatar_url TEXT,
author_is_verified BOOLEAN DEFAULT FALSE,

-- NEW: Brand/Keyword fields
brand_name VARCHAR(100),
keyword VARCHAR(200),
```

### post_comments (New Table)

```sql
CREATE TABLE post_comments (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(50) NOT NULL REFERENCES post_analytics(id) ON DELETE CASCADE,
    comment_id VARCHAR(100),

    text TEXT NOT NULL,
    author_name VARCHAR(200),
    likes INTEGER DEFAULT 0,

    sentiment VARCHAR(10),
    sentiment_score FLOAT,

    commented_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Risks / Trade-offs

### Risk 1: Storage Growth

- **Risk**: Lưu content_text và transcription tăng storage đáng kể
- **Mitigation**: TEXT columns được compress tự động bởi PostgreSQL

### Risk 2: Migration on Large Table

- **Risk**: ALTER TABLE trên `post_analytics` có thể slow nếu table lớn
- **Mitigation**:
  - Tất cả columns nullable → không cần rewrite table
  - Chạy migration off-peak hours

### Risk 3: Comment Volume

- **Risk**: Số lượng comments có thể rất lớn
- **Mitigation**:
  - Index trên `post_id` cho fast lookup
  - Có thể partition theo thời gian sau này

## Migration Plan

### Phase 1: Schema Migration

1. Create migration for new columns
2. Create migration for `post_comments` table
3. Create migration for indexes
4. Apply migrations to dev/staging

### Phase 2: Code Deployment

1. Deploy updated consumer code
2. New events will populate new fields
3. Old data remains with NULL values

### Rollback

- Drop new columns (data loss acceptable for new fields)
- Drop `post_comments` table
- No impact on existing functionality

## Open Questions

1. **Comment sentiment analysis**: Có cần phân tích sentiment cho từng comment không?

   - Recommendation: Có, để aggregate comment sentiment

2. **Comment deduplication**: Có cần unique constraint trên `(post_id, comment_id)`?

   - Recommendation: Có, để tránh duplicate khi re-process

3. **Hashtags format**: JSONB array hay comma-separated string?
   - Decision: JSONB array để query linh hoạt hơn
