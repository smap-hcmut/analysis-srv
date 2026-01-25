# Crawler → Analyst Data Contract

**Ngày tạo:** 2025-12-17  
**Cập nhật:** 2025-12-18  
**Phiên bản:** 2.0  
**Mục đích:** Định nghĩa chi tiết cấu trúc dữ liệu mà Analytics Service mong muốn nhận từ Crawler Service

---

## 1. Tổng quan Flow

```
Crawler ──(upload JSON)──► MinIO
    │
    └──(data.collected event)──► Analytics Service
                                     │
                                     ├── Download batch từ MinIO
                                     ├── Parse & validate structure
                                     ├── Process từng item (sentiment, intent, impact)
                                     └── Save to DB (post_analytics + post_comments)
```

---

## 2. Event Message (RabbitMQ)

### 2.1. Exchange & Routing

| Component   | Value                      |
| ----------- | -------------------------- |
| Exchange    | `smap.events`              |
| Routing Key | `data.collected`           |
| Queue       | `analytics.data.collected` |

### 2.2. Event Envelope Schema

```json
{
  "event_id": "string",
  "event_type": "data.collected",
  "timestamp": "string (ISO 8601)",
  "payload": {
    "minio_path": "string",
    "project_id": "string (required)",
    "job_id": "string",
    "batch_index": "integer",
    "content_count": "integer",
    "platform": "string",
    "task_type": "string",
    "brand_name": "string",
    "keyword": "string"
  }
}
```

### 2.3. Event Fields Chi Tiết

| Field                   | Type      | Required   | Description                  | Example                                            |
| ----------------------- | --------- | ---------- | ---------------------------- | -------------------------------------------------- |
| `event_id`              | `string`  | ✅         | Unique event identifier      | `"evt_abc123"`                                     |
| `event_type`            | `string`  | ✅         | Phải là `"data.collected"`   | `"data.collected"`                                 |
| `timestamp`             | `string`  | ✅         | ISO 8601 format với timezone | `"2025-12-17T10:00:00Z"`                           |
| `payload.minio_path`    | `string`  | ✅         | Đường dẫn file trong MinIO   | `"crawl-results/tiktok/2025/12/17/batch_001.json"` |
| `payload.project_id`    | `string`  | ✅ 🆕      | UUID của project             | `"proj_xyz"`                                       |
| `payload.job_id`        | `string`  | ✅         | Job identifier               | `"proj_xyz-brand-0"`                               |
| `payload.batch_index`   | `integer` | ✅         | Số thứ tự batch (0-indexed)  | `0`                                                |
| `payload.content_count` | `integer` | ✅         | Số lượng items trong batch   | `50`                                               |
| `payload.platform`      | `string`  | ✅         | Platform nguồn (lowercase)   | `"tiktok"` hoặc `"youtube"`                        |
| `payload.task_type`     | `string`  | ✅         | Loại task                    | `"research_and_crawl"`                             |
| `payload.brand_name`    | `string`  | ✅ **NEW** | Tên brand đang crawl         | `"VinFast"` hoặc `"Toyota"`                        |
| `payload.keyword`       | `string`  | ✅         | Keyword đã crawl             | `"VinFast VF8"`                                    |

> ⚠️ **NEW v2.0:**
>
> - `project_id` giờ là **REQUIRED** (không còn support dry-run)
> - Thêm `brand_name` để phân biệt brand/competitor trong cùng 1 project

---

## 3. MinIO Batch Data Structure

### 3.1. File Format

- **Format:** JSON Array
- **Compression:** Zstd (recommended, level 2)
- **Encoding:** UTF-8

### 3.2. Compression Metadata (Required nếu compressed)

```yaml
x-amz-meta-compressed: "true"
x-amz-meta-compression-algorithm: "zstd"
x-amz-meta-compression-level: "2"
x-amz-meta-original-size: "102400"
x-amz-meta-compressed-size: "25600"
```

### 3.3. Batch Array Schema

```json
[
  {
    /* Item 1 - CrawlerContent */
  },
  {
    /* Item 2 - CrawlerContent */
  }
]
```

---

## 4. CrawlerContent Item Schema (⭐ QUAN TRỌNG)

Đây là cấu trúc chính mà Analytics Service mong muốn nhận cho mỗi item trong batch.

### 4.1. Top-Level Structure

```json
{
  "meta": {
    /* CrawlerContentMeta */
  },
  "content": {
    /* CrawlerContentData */
  },
  "interaction": {
    /* CrawlerContentInteraction */
  },
  "author": {
    /* CrawlerContentAuthor */
  },
  "comments": [
    /* Array of CrawlerComment */
  ]
}
```

### 4.2. Legend

| Icon | Meaning                                               |
| ---- | ----------------------------------------------------- |
| ✅   | Required - Bắt buộc phải có                           |
| 💾   | Saved to DB - Được lưu vào database                   |
| 🔄   | Processing only - Chỉ dùng để phân tích, KHÔNG lưu DB |
| 🆕   | New in v2.0                                           |

---

### 4.3. `meta` Object (Required)

| Field           | Type             | Required | Saved | Description                  | DB Column                      |
| --------------- | ---------------- | -------- | ----- | ---------------------------- | ------------------------------ |
| `id`            | `string`         | ✅       | 💾    | Unique content ID            | `post_analytics.id`            |
| `platform`      | `string`         | ✅       | 💾    | Platform nguồn (uppercase)   | `post_analytics.platform`      |
| `fetch_status`  | `string`         | ✅       | 💾    | Trạng thái fetch             | `post_analytics.fetch_status`  |
| `published_at`  | `string`         | ✅       | 💾    | Thời gian publish (ISO 8601) | `post_analytics.published_at`  |
| `permalink`     | `string \| null` | ✅ 🆕    | 💾    | URL gốc của content          | `post_analytics.permalink`     |
| `error_code`    | `string`         | ⚠️       | 💾    | Mã lỗi (required nếu error)  | `post_analytics.error_code`    |
| `error_message` | `string \| null` | ❌       | 💾    | Mô tả lỗi                    | `post_analytics.fetch_error`   |
| `error_details` | `object \| null` | ❌       | 💾    | Chi tiết lỗi bổ sung         | `post_analytics.error_details` |

**Ví dụ `meta` cho success item:**

```json
{
  "id": "7441234567890123456",
  "platform": "TIKTOK",
  "fetch_status": "success",
  "published_at": "2025-12-10T08:00:00Z",
  "permalink": "https://tiktok.com/@techreviewer/video/7441234567890123456"
}
```

**Ví dụ `meta` cho error item:**

```json
{
  "id": "7441234567890123456",
  "platform": "TIKTOK",
  "fetch_status": "error",
  "error_code": "CONTENT_REMOVED",
  "error_message": "Video has been removed",
  "permalink": "https://tiktok.com/@user/video/7441234567890123456"
}
```

---

### 4.4. `content` Object (Required cho success items)

| Field           | Type                    | Required | Saved | Description                  | DB Column                              |
| --------------- | ----------------------- | -------- | ----- | ---------------------------- | -------------------------------------- |
| `text`          | `string`                | ✅       | 💾 🆕 | Nội dung text chính          | `post_analytics.content_text`          |
| `transcription` | `string \| null`        | ❌       | 💾 🆕 | Transcription từ audio/video | `post_analytics.content_transcription` |
| `duration`      | `integer \| null`       | ❌       | 💾 🆕 | Thời lượng video (giây)      | `post_analytics.media_duration`        |
| `hashtags`      | `array[string] \| null` | ❌       | 💾 🆕 | Danh sách hashtags           | `post_analytics.hashtags` (JSONB)      |

**Ví dụ:**

```json
{
  "text": "Review chi tiết VinFast VF8 sau 1 tháng sử dụng #vinfast #vf8",
  "transcription": "Xin chào các bạn, hôm nay mình sẽ review...",
  "duration": 180,
  "hashtags": ["vinfast", "vf8", "review"]
}
```

---

### 4.5. `interaction` Object (Required)

| Field            | Type      | Required | Saved | Description               | DB Column       |
| ---------------- | --------- | -------- | ----- | ------------------------- | --------------- |
| `views`          | `integer` | ✅       | 💾    | Số lượt xem               | `view_count`    |
| `likes`          | `integer` | ✅       | 💾    | Số lượt like              | `like_count`    |
| `comments_count` | `integer` | ✅       | 💾    | Số lượng comments         | `comment_count` |
| `shares`         | `integer` | ❌       | 💾    | Số lượt share (default 0) | `share_count`   |
| `saves`          | `integer` | ❌       | 💾    | Số lượt save (default 0)  | `save_count`    |

**Ví dụ:**

```json
{
  "views": 10000,
  "likes": 500,
  "comments_count": 50,
  "shares": 100,
  "saves": 25
}
```

---

### 4.6. `author` Object (Required) 🆕 EXPANDED

| Field         | Type             | Required | Saved | Description           | DB Column                           |
| ------------- | ---------------- | -------- | ----- | --------------------- | ----------------------------------- |
| `id`          | `string`         | ✅ 🆕    | 💾    | Author ID từ platform | `post_analytics.author_id`          |
| `name`        | `string`         | ✅ 🆕    | 💾    | Tên hiển thị          | `post_analytics.author_name`        |
| `username`    | `string`         | ✅ 🆕    | 💾    | Username/handle       | `post_analytics.author_username`    |
| `avatar_url`  | `string \| null` | ❌       | 💾 🆕 | URL avatar            | `post_analytics.author_avatar_url`  |
| `followers`   | `integer`        | ✅       | 💾    | Số followers          | `follower_count`                    |
| `is_verified` | `boolean`        | ❌       | 💾 🆕 | Tài khoản verified    | `post_analytics.author_is_verified` |

**Ví dụ:**

```json
{
  "id": "author_456",
  "name": "Tech Reviewer",
  "username": "@techreviewer",
  "avatar_url": "https://p16-sign.tiktokcdn.com/avatar/xxx",
  "followers": 50000,
  "is_verified": true
}
```

---

### 4.7. `comments` Array (Optional) 🆕 NOW SAVED

| Field         | Type             | Required | Saved | Description              | DB Table                     |
| ------------- | ---------------- | -------- | ----- | ------------------------ | ---------------------------- |
| `id`          | `string`         | ❌       | 💾 🆕 | Comment ID từ platform   | `post_comments.comment_id`   |
| `text`        | `string`         | ✅       | 💾 🆕 | Nội dung comment         | `post_comments.text`         |
| `author_name` | `string \| null` | ❌       | 💾 🆕 | Tên người comment        | `post_comments.author_name`  |
| `likes`       | `integer`        | ❌       | 💾 🆕 | Số likes của comment     | `post_comments.likes`        |
| `created_at`  | `string \| null` | ❌       | 💾 🆕 | Thời gian tạo (ISO 8601) | `post_comments.commented_at` |

> 🆕 **NEW v2.0:** Comments giờ được lưu vào bảng riêng `post_comments` và sẽ được phân tích sentiment riêng.

**Ví dụ:**

```json
[
  {
    "id": "cmt_001",
    "text": "Video hay quá! Cảm ơn bạn đã review",
    "author_name": "User123",
    "likes": 10,
    "created_at": "2025-12-11T10:00:00Z"
  },
  {
    "id": "cmt_002",
    "text": "Mình cũng đang cân nhắc mua VF8",
    "author_name": "User456",
    "likes": 5,
    "created_at": "2025-12-11T11:00:00Z"
  }
]
```

---

## 5. Complete Example

### 5.1. Success Item (Full - Recommended for v2.0)

```json
{
  "meta": {
    "id": "7441234567890123456",
    "platform": "TIKTOK",
    "fetch_status": "success",
    "published_at": "2025-12-10T08:00:00Z",
    "permalink": "https://tiktok.com/@techreviewer/video/7441234567890123456"
  },
  "content": {
    "text": "Review chi tiết VinFast VF8 sau 1 tháng sử dụng. Xe chạy êm, pin trâu! #vinfast #vf8 #review",
    "transcription": "Xin chào các bạn, hôm nay mình sẽ review chi tiết chiếc VinFast VF8...",
    "duration": 180,
    "hashtags": ["vinfast", "vf8", "review"]
  },
  "interaction": {
    "views": 10000,
    "likes": 500,
    "comments_count": 50,
    "shares": 100,
    "saves": 25
  },
  "author": {
    "id": "author_456",
    "name": "Tech Reviewer",
    "username": "@techreviewer",
    "avatar_url": "https://p16-sign.tiktokcdn.com/avatar/xxx",
    "followers": 50000,
    "is_verified": true
  },
  "comments": [
    {
      "id": "cmt_001",
      "text": "Video hay quá! Cảm ơn bạn đã review",
      "author_name": "User123",
      "likes": 10,
      "created_at": "2025-12-11T10:00:00Z"
    },
    {
      "id": "cmt_002",
      "text": "Mình cũng đang cân nhắc mua VF8",
      "author_name": "User456",
      "likes": 5,
      "created_at": "2025-12-11T11:00:00Z"
    }
  ]
}
```

### 5.2. Error Item

```json
{
  "meta": {
    "id": "7441234567890999999",
    "platform": "TIKTOK",
    "fetch_status": "error",
    "error_code": "CONTENT_REMOVED",
    "error_message": "Video has been removed by the creator",
    "permalink": "https://tiktok.com/@user/video/7441234567890999999"
  }
}
```

---

## 6. Error Codes (Supported)

| Category          | Error Codes                                                      |
| ----------------- | ---------------------------------------------------------------- |
| **Rate Limiting** | `RATE_LIMITED`, `AUTH_FAILED`, `ACCESS_DENIED`                   |
| **Content**       | `CONTENT_REMOVED`, `CONTENT_NOT_FOUND`, `CONTENT_UNAVAILABLE`    |
| **Network**       | `NETWORK_ERROR`, `TIMEOUT`, `CONNECTION_REFUSED`, `DNS_ERROR`    |
| **Parsing**       | `PARSE_ERROR`, `INVALID_URL`, `INVALID_RESPONSE`                 |
| **Media**         | `MEDIA_DOWNLOAD_FAILED`, `MEDIA_TOO_LARGE`, `MEDIA_FORMAT_ERROR` |
| **Storage**       | `STORAGE_ERROR`, `UPLOAD_FAILED`, `DATABASE_ERROR`               |
| **Generic**       | `UNKNOWN_ERROR`, `INTERNAL_ERROR`                                |

---

## 7. Batch Size Requirements

| Platform | Expected Size | Notes            |
| -------- | ------------- | ---------------- |
| TikTok   | 50 items      | Warning nếu khác |
| YouTube  | 20 items      | Warning nếu khác |

---

## 8. Fields được Analytics Enrich từ Event

Analytics Service sẽ tự động enrich các fields sau từ event metadata:

| Field              | Source                        | Description               | DB Column                         |
| ------------------ | ----------------------------- | ------------------------- | --------------------------------- |
| `job_id`           | `event.payload.job_id`        | Job identifier            | `post_analytics.job_id`           |
| `batch_index`      | `event.payload.batch_index`   | Batch sequence number     | `post_analytics.batch_index`      |
| `task_type`        | `event.payload.task_type`     | Task type                 | `post_analytics.task_type`        |
| `brand_name`       | `event.payload.brand_name` 🆕 | Brand name                | `post_analytics.brand_name`       |
| `keyword`          | `event.payload.keyword`       | Search keyword            | `post_analytics.keyword`          |
| `crawled_at`       | `event.timestamp`             | Crawl timestamp           | `post_analytics.crawled_at`       |
| `pipeline_version` | Auto-generated                | `"crawler_{platform}_v3"` | `post_analytics.pipeline_version` |
| `project_id`       | Extracted from `job_id`       | Project identifier        | `post_analytics.project_id`       |

---

## 9. Database Schema (Analytics Service)

### 9.1. Table: `post_analytics` (Extended)

```sql
-- Existing fields
id VARCHAR(50) PRIMARY KEY,
project_id UUID,
platform VARCHAR(20) NOT NULL,
published_at TIMESTAMP NOT NULL,
analyzed_at TIMESTAMP,

-- Analysis results (unchanged)
overall_sentiment VARCHAR(10),
overall_sentiment_score FLOAT,
...

-- Interaction metrics (unchanged)
view_count INTEGER,
like_count INTEGER,
comment_count INTEGER,
share_count INTEGER,
save_count INTEGER,
follower_count INTEGER,

-- 🆕 NEW: Author info (denormalized)
author_id VARCHAR(100),
author_name VARCHAR(200),
author_username VARCHAR(100),
author_avatar_url TEXT,
author_is_verified BOOLEAN DEFAULT FALSE,

-- 🆕 NEW: Content storage
content_text TEXT,
content_transcription TEXT,
permalink TEXT,
hashtags JSONB,
media_duration INTEGER,

-- 🆕 NEW: Brand/Keyword for filtering
brand_name VARCHAR(100),
keyword VARCHAR(200),

-- Batch context (existing)
job_id VARCHAR(100),
batch_index INTEGER,
task_type VARCHAR(30),
crawled_at TIMESTAMP,
pipeline_version VARCHAR(50),

-- Error tracking (existing)
fetch_status VARCHAR(10),
error_code VARCHAR(50),
fetch_error TEXT,
error_details JSONB
```

### 9.2. Table: `post_comments` (NEW)

```sql
CREATE TABLE post_comments (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(50) NOT NULL REFERENCES post_analytics(id),
    comment_id VARCHAR(100),  -- Original ID from platform

    -- Content
    text TEXT NOT NULL,
    author_name VARCHAR(200),
    likes INTEGER DEFAULT 0,

    -- Analysis results (filled by Analytics)
    sentiment VARCHAR(10),        -- POSITIVE/NEGATIVE/NEUTRAL
    sentiment_score FLOAT,

    -- Timestamps
    commented_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_post_comments_post_id (post_id),
    INDEX idx_post_comments_sentiment (sentiment)
);
```

---

## 10. Validation Checklist cho Crawler

### Event Message (Tất cả đều REQUIRED)

- [ ] `event_id` là unique
- [ ] `event_type` = `"data.collected"`
- [ ] `timestamp` đúng format ISO 8601
- [ ] `payload.minio_path` không rỗng
- [ ] `payload.project_id` không rỗng (UUID format) 🆕
- [ ] `payload.job_id` không rỗng
- [ ] `payload.batch_index` >= 0
- [ ] `payload.content_count` > 0
- [ ] `payload.platform` là `"tiktok"` hoặc `"youtube"`
- [ ] `payload.task_type` = `"research_and_crawl"`
- [ ] `payload.brand_name` không rỗng 🆕
- [ ] `payload.keyword` không rỗng

### Batch Item - Success

| Field                        | Validation         | Required             |
| ---------------------------- | ------------------ | -------------------- |
| `meta.id`                    | Không rỗng, unique | ✅                   |
| `meta.platform`              | Không rỗng         | ✅                   |
| `meta.fetch_status`          | = `"success"`      | ✅                   |
| `meta.published_at`          | ISO 8601 format    | ✅                   |
| `meta.permalink`             | Valid URL          | ✅ 🆕                |
| `content.text`               | Không rỗng         | ✅                   |
| `content.transcription`      | String             | ❌                   |
| `content.duration`           | >= 0               | ❌                   |
| `content.hashtags`           | Array of strings   | ❌                   |
| `interaction.views`          | >= 0               | ✅                   |
| `interaction.likes`          | >= 0               | ✅                   |
| `interaction.comments_count` | >= 0               | ✅                   |
| `interaction.shares`         | >= 0               | ❌                   |
| `interaction.saves`          | >= 0               | ❌                   |
| `author.id`                  | Không rỗng         | ✅ 🆕                |
| `author.name`                | Không rỗng         | ✅ 🆕                |
| `author.username`            | Không rỗng         | ✅ 🆕                |
| `author.avatar_url`          | Valid URL          | ❌                   |
| `author.followers`           | >= 0               | ✅                   |
| `author.is_verified`         | Boolean            | ❌                   |
| `comments[].text`            | Không rỗng         | ✅ (nếu có comments) |
| `comments[].id`              | String             | ❌                   |
| `comments[].author_name`     | String             | ❌                   |
| `comments[].likes`           | >= 0               | ❌                   |
| `comments[].created_at`      | ISO 8601           | ❌                   |

### Batch Item - Error

| Field                | Validation     | Required |
| -------------------- | -------------- | -------- |
| `meta.id`            | Không rỗng     | ✅       |
| `meta.platform`      | Không rỗng     | ✅       |
| `meta.fetch_status`  | = `"error"`    | ✅       |
| `meta.error_code`    | Supported code | ✅       |
| `meta.error_message` | String         | ❌       |
| `meta.permalink`     | Valid URL      | ❌       |

---

## 11. Migration Notes (v1.0 → v2.0)

### Breaking Changes

1. **Event payload**: Thêm `brand_name` (required)
2. **Author fields**: `id`, `name`, `username` giờ là required
3. **Permalink**: Giờ là required cho success items

### New Features

1. **Content storage**: `text`, `transcription`, `hashtags`, `duration` được lưu
2. **Author info**: Full author profile được lưu
3. **Comments table**: Comments được lưu riêng với sentiment analysis
4. **Brand/Keyword filtering**: Hỗ trợ filter theo brand và keyword

### Backward Compatibility

- Analytics Service sẽ handle gracefully nếu thiếu new fields
- Old format vẫn được xử lý nhưng sẽ có NULL values cho new fields

---

## 12. Version History

| Version | Date       | Changes                                                    |
| ------- | ---------- | ---------------------------------------------------------- |
| 1.0     | 2025-12-17 | Initial contract                                           |
| 2.0     | 2025-12-18 | Added brand_name, expanded author/content/comments storage |
