# Analytics Service - Entity Relationship Diagram

**Ngày tạo:** 2025-12-18  
**Mục đích:** Mô tả cấu trúc database của Analytics Service sau khi implement Contract v2.0

---

## 1. ERD Overview

```mermaid
erDiagram
    post_analytics ||--o{ post_comments : "has many"
    post_analytics ||--o{ crawl_errors : "may have"

    post_analytics {
        string id PK "Content ID từ platform"
        uuid project_id FK "UUID của project"
        string platform "TIKTOK | YOUTUBE"
        timestamp published_at "Thời gian publish"
        timestamp analyzed_at "Thời gian phân tích"

        string overall_sentiment "POSITIVE | NEGATIVE | NEUTRAL"
        float overall_sentiment_score "-1.0 to 1.0"
        float overall_confidence "0.0 to 1.0"

        string primary_intent "REVIEW | COMPLAINT | QUESTION..."
        float intent_confidence "0.0 to 1.0"

        float impact_score "0 to 100"
        string risk_level "LOW | MEDIUM | HIGH | CRITICAL"
        boolean is_viral "Viral detection"
        boolean is_kol "KOL detection"

        jsonb aspects_breakdown "Aspect-based sentiment"
        jsonb keywords "Extracted keywords"
        jsonb sentiment_probabilities "Sentiment probs"
        jsonb impact_breakdown "Impact calculation details"

        integer view_count "Số lượt xem"
        integer like_count "Số lượt like"
        integer comment_count "Số comments"
        integer share_count "Số lượt share"
        integer save_count "Số lượt save"
        integer follower_count "Followers của author"

        text content_text "Nội dung bài viết"
        text content_transcription "Transcription audio/video"
        integer media_duration "Thời lượng video (giây)"
        jsonb hashtags "Danh sách hashtags"
        text permalink "URL gốc của content"

        string author_id "Author ID từ platform"
        string author_name "Tên hiển thị"
        string author_username "Username/handle"
        text author_avatar_url "URL avatar"
        boolean author_is_verified "Verified account"

        string brand_name "Tên brand đang crawl"
        string keyword "Keyword đã search"

        string job_id "Job identifier"
        integer batch_index "Batch sequence number"
        string task_type "research_and_crawl"
        string keyword_source "Legacy keyword field"
        timestamp crawled_at "Thời gian crawl"
        string pipeline_version "crawler_tiktok_v3"

        string fetch_status "success | error"
        string error_code "Error code nếu có"
        text fetch_error "Error message"
        jsonb error_details "Chi tiết lỗi"

        integer processing_time_ms "Thời gian xử lý"
        string model_version "Model version"
    }

    post_comments {
        serial id PK "Auto increment ID"
        string post_id FK "FK to post_analytics"
        string comment_id "Comment ID từ platform"

        text text "Nội dung comment"
        string author_name "Tên người comment"
        integer likes "Số likes của comment"

        string sentiment "POSITIVE | NEGATIVE | NEUTRAL"
        float sentiment_score "-1.0 to 1.0"

        timestamp commented_at "Thời gian tạo comment"
        timestamp created_at "Thời gian lưu vào DB"
    }

    crawl_errors {
        serial id PK "Auto increment ID"
        string content_id "Content ID bị lỗi"
        uuid project_id FK "UUID của project"
        string job_id "Job identifier"
        string platform "TIKTOK | YOUTUBE"

        string error_code "Mã lỗi chuẩn"
        string error_category "Phân loại lỗi"
        text error_message "Mô tả lỗi"
        jsonb error_details "Chi tiết lỗi"

        text permalink "URL của content"
        timestamp created_at "Thời gian ghi nhận"
    }
```

---

## 2. Table Details

### 2.1. `post_analytics` - Main Analytics Table

```mermaid
classDiagram
    class post_analytics {
        +String id [PK]
        +UUID project_id
        +String platform

        -- Timestamps --
        +Timestamp published_at
        +Timestamp analyzed_at

        -- Analysis Results --
        +String overall_sentiment
        +Float overall_sentiment_score
        +Float overall_confidence
        +String primary_intent
        +Float intent_confidence
        +Float impact_score
        +String risk_level
        +Boolean is_viral
        +Boolean is_kol

        -- JSONB Data --
        +JSONB aspects_breakdown
        +JSONB keywords
        +JSONB sentiment_probabilities
        +JSONB impact_breakdown
        +JSONB hashtags

        -- Interaction Metrics --
        +Integer view_count
        +Integer like_count
        +Integer comment_count
        +Integer share_count
        +Integer save_count
        +Integer follower_count

        -- Content [NEW] --
        +Text content_text
        +Text content_transcription
        +Integer media_duration
        +Text permalink

        -- Author [NEW] --
        +String author_id
        +String author_name
        +String author_username
        +Text author_avatar_url
        +Boolean author_is_verified

        -- Brand/Keyword [NEW] --
        +String brand_name
        +String keyword

        -- Batch Context --
        +String job_id
        +Integer batch_index
        +String task_type
        +String keyword_source
        +Timestamp crawled_at
        +String pipeline_version

        -- Error Tracking --
        +String fetch_status
        +String error_code
        +Text fetch_error
        +JSONB error_details

        -- Processing --
        +Integer processing_time_ms
        +String model_version
    }
```

### 2.2. `post_comments` - Comments Table (NEW)

```mermaid
classDiagram
    class post_comments {
        +Serial id [PK]
        +String post_id [FK]
        +String comment_id

        -- Content --
        +Text text
        +String author_name
        +Integer likes

        -- Analysis --
        +String sentiment
        +Float sentiment_score

        -- Timestamps --
        +Timestamp commented_at
        +Timestamp created_at
    }
```

### 2.3. `crawl_errors` - Error Tracking Table

```mermaid
classDiagram
    class crawl_errors {
        +Serial id [PK]
        +String content_id
        +UUID project_id
        +String job_id
        +String platform

        -- Error Details --
        +String error_code
        +String error_category
        +Text error_message
        +JSONB error_details

        -- Reference --
        +Text permalink
        +Timestamp created_at
    }
```

---

## 3. Relationships

```mermaid
flowchart LR
    subgraph Analytics Service Database
        PA[post_analytics]
        PC[post_comments]
        CE[crawl_errors]
    end

    subgraph External References
        PS[Project Service]
    end

    PA -->|1:N| PC
    PA -.->|0:N| CE
    PA -.->|project_id| PS
    CE -.->|project_id| PS
```

| Relationship              | Type | Description                                |
| ------------------------- | ---- | ------------------------------------------ |
| post_analytics → comments | 1:N  | Một post có nhiều comments                 |
| post_analytics → errors   | 0:N  | Một post có thể có error record (nếu fail) |
| post_analytics → project  | N:1  | Nhiều posts thuộc một project (external)   |

---

## 4. Indexes

### 4.1. `post_analytics` Indexes

| Index Name                        | Column(s)      | Purpose              |
| --------------------------------- | -------------- | -------------------- |
| `pk_post_analytics`               | `id`           | Primary key          |
| `idx_post_analytics_job_id`       | `job_id`       | Query by job         |
| `idx_post_analytics_fetch_status` | `fetch_status` | Filter success/error |
| `idx_post_analytics_task_type`    | `task_type`    | Filter by task type  |
| `idx_post_analytics_error_code`   | `error_code`   | Error analysis       |
| `idx_post_analytics_brand_name`   | `brand_name`   | 🆕 Filter by brand   |
| `idx_post_analytics_keyword`      | `keyword`      | 🆕 Filter by keyword |
| `idx_post_analytics_author_id`    | `author_id`    | 🆕 Group by author   |
| `idx_post_analytics_project_id`   | `project_id`   | Filter by project    |
| `idx_post_analytics_platform`     | `platform`     | Filter by platform   |
| `idx_post_analytics_published_at` | `published_at` | Time-series queries  |

### 4.2. `post_comments` Indexes

| Index Name                       | Column(s)      | Purpose             |
| -------------------------------- | -------------- | ------------------- |
| `pk_post_comments`               | `id`           | Primary key         |
| `idx_post_comments_post_id`      | `post_id`      | Join with post      |
| `idx_post_comments_sentiment`    | `sentiment`    | Filter by sentiment |
| `idx_post_comments_commented_at` | `commented_at` | Time-series queries |

### 4.3. `crawl_errors` Indexes

| Index Name                    | Column(s)    | Purpose             |
| ----------------------------- | ------------ | ------------------- |
| `pk_crawl_errors`             | `id`         | Primary key         |
| `idx_crawl_errors_project_id` | `project_id` | Filter by project   |
| `idx_crawl_errors_error_code` | `error_code` | Error analysis      |
| `idx_crawl_errors_created_at` | `created_at` | Time-series queries |
| `idx_crawl_errors_job_id`     | `job_id`     | Query by job        |

---

## 5. Data Flow

```mermaid
flowchart TB
    subgraph Crawler Service
        CR[Crawler]
    end

    subgraph Message Queue
        MQ[RabbitMQ]
        MINIO[MinIO Storage]
    end

    subgraph Analytics Service
        CONS[Consumer]
        ORCH[Orchestrator]
        SENT[Sentiment Analyzer]
        IMP[Impact Calculator]

        subgraph Database
            PA[(post_analytics)]
            PC[(post_comments)]
            CE[(crawl_errors)]
        end
    end

    CR -->|Upload batch| MINIO
    CR -->|data.collected event| MQ

    MQ -->|Consume event| CONS
    CONS -->|Download batch| MINIO
    CONS -->|Process item| ORCH

    ORCH -->|Analyze| SENT
    ORCH -->|Calculate| IMP
    ORCH -->|Save post| PA

    CONS -->|Save comments| PC
    CONS -->|Save errors| CE
```

---

## 6. Field Groups (NEW vs Existing)

### 🆕 NEW Fields (Contract v2.0)

```mermaid
mindmap
    root((NEW Fields))
        Content
            content_text
            content_transcription
            media_duration
            hashtags
            permalink
        Author
            author_id
            author_name
            author_username
            author_avatar_url
            author_is_verified
        Brand/Keyword
            brand_name
            keyword
        Comments Table
            post_comments
```

### ✅ Existing Fields

```mermaid
mindmap
    root((Existing))
        Identifiers
            id
            project_id
            platform
        Analysis
            overall_sentiment
            primary_intent
            impact_score
            risk_level
        Metrics
            view_count
            like_count
            comment_count
            share_count
            save_count
            follower_count
        Batch Context
            job_id
            batch_index
            task_type
            keyword_source
        Error Tracking
            fetch_status
            error_code
            fetch_error
```

---

## 7. Sample Queries

### Query posts by brand and keyword

```sql
SELECT id, content_text, author_name, overall_sentiment, impact_score
FROM post_analytics
WHERE project_id = 'uuid-here'
  AND brand_name = 'VinFast'
  AND keyword = 'VinFast VF8'
ORDER BY published_at DESC
LIMIT 50;
```

### Query posts with comments

```sql
SELECT
    p.id,
    p.content_text,
    p.author_name,
    COUNT(c.id) as comment_count,
    AVG(c.sentiment_score) as avg_comment_sentiment
FROM post_analytics p
LEFT JOIN post_comments c ON p.id = c.post_id
WHERE p.project_id = 'uuid-here'
GROUP BY p.id
ORDER BY p.impact_score DESC;
```

### Aggregate by brand

```sql
SELECT
    brand_name,
    COUNT(*) as post_count,
    AVG(impact_score) as avg_impact,
    SUM(view_count) as total_views
FROM post_analytics
WHERE project_id = 'uuid-here'
GROUP BY brand_name;
```
