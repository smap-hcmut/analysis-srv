# Analytics Service Integration Contract

## Overview

Tài liệu này mô tả các yêu cầu chi tiết mà các system tương tác với Analytics Service phải tuân thủ để đảm bảo integration hoạt động chính xác.

## Producers (Crawler Services)

### Event Schema Requirements

Crawler services **PHẢI** emit events theo schema sau:

```json
{
  "event_id": "string (required, unique)",
  "event_type": "data.collected (required, exact value)",
  "timestamp": "ISO 8601 format (required)",
  "payload": {
    "minio_path": "string (required, format: bucket/path/to/file.json)",
    "project_id": "string (optional, UUID format)",
    "job_id": "string (required)",
    "batch_index": "integer (required, >= 0)",
    "content_count": "integer (required, > 0)",
    "platform": "string (required, lowercase: tiktok|youtube)",
    "task_type": "string (optional)",
    "keyword": "string (optional)"
  }
}
```

### Job ID Format Requirements

Job ID **PHẢI** tuân theo một trong các format sau:

| Type            | Format                                   | Example                                |
| --------------- | ---------------------------------------- | -------------------------------------- |
| Brand task      | `{project_id}-brand-{index}`             | `proj_abc-brand-0`                     |
| Competitor task | `{project_id}-{competitor_name}-{index}` | `proj_abc-toyota-5`                    |
| Dry-run task    | UUID v4                                  | `550e8400-e29b-41d4-a716-446655440000` |

**Rules:**

- `project_id` có thể chứa hyphens
- `index` **PHẢI** là số nguyên không âm
- Dry-run tasks sử dụng UUID, không có project association

### MinIO Path Requirements

MinIO path **PHẢI** tuân theo format:

```
{bucket}/{platform}/{year}/{month}/{day}/{filename}.json
```

**Example:** `crawl-results/tiktok/2025/12/06/batch_001.json`

**Rules:**

- Bucket name **PHẢI** là `crawl-results` (configurable)
- Path **PHẢI** chứa ít nhất 1 slash để tách bucket và object path
- File **PHẢI** là JSON format (có thể compressed với zstd)

### Batch Data Requirements

Batch file trong MinIO **PHẢI** là JSON array hoặc single object:

```json
[
  {
    "meta": {
      "id": "string (required, unique content ID)",
      "platform": "string (required)",
      "fetch_status": "success|error (required)",
      "error_code": "string (required if fetch_status=error)",
      "error_message": "string (optional)",
      "error_details": "object (optional)",
      "permalink": "string (optional)"
    },
    "content": {
      "text": "string (required for success items)"
    },
    "interactions": {
      "likes": "integer",
      "comments_count": "integer",
      "shares": "integer",
      "views": "integer"
    },
    "author": {
      "followers": "integer",
      "is_verified": "boolean"
    }
  }
]
```

### Error Item Requirements

Khi crawler gặp lỗi, item **PHẢI** có:

```json
{
  "meta": {
    "id": "content_id",
    "platform": "tiktok",
    "fetch_status": "error",
    "error_code": "RATE_LIMITED",
    "error_message": "Too many requests",
    "error_details": {
      "retry_after": 60
    }
  }
}
```

**Supported Error Codes:**

| Category      | Codes                                                            |
| ------------- | ---------------------------------------------------------------- |
| Rate Limiting | `RATE_LIMITED`, `AUTH_FAILED`, `ACCESS_DENIED`                   |
| Content       | `CONTENT_REMOVED`, `CONTENT_NOT_FOUND`, `CONTENT_UNAVAILABLE`    |
| Network       | `NETWORK_ERROR`, `TIMEOUT`, `CONNECTION_REFUSED`, `DNS_ERROR`    |
| Parsing       | `PARSE_ERROR`, `INVALID_URL`, `INVALID_RESPONSE`                 |
| Media         | `MEDIA_DOWNLOAD_FAILED`, `MEDIA_TOO_LARGE`, `MEDIA_FORMAT_ERROR` |
| Storage       | `STORAGE_ERROR`, `UPLOAD_FAILED`, `DATABASE_ERROR`               |
| Generic       | `UNKNOWN_ERROR`, `INTERNAL_ERROR`                                |

### Batch Size Requirements

| Platform | Expected Size | Tolerance            |
| -------- | ------------- | -------------------- |
| TikTok   | 50 items      | Warning if different |
| YouTube  | 20 items      | Warning if different |

**Note:** Analytics Service sẽ xử lý bất kỳ batch size nào, nhưng sẽ log warning nếu khác expected.

## RabbitMQ Requirements

### Exchange Configuration

```yaml
Exchange:
  name: smap.events
  type: topic
  durable: true
```

### Routing Key

```
data.collected
```

### Queue Binding

Analytics Service sẽ tự động:

1. Declare queue `analytics.data.collected`
2. Bind queue to exchange với routing key `data.collected`

### Message Properties

```yaml
Content-Type: application/json
Delivery-Mode: 2 (persistent)
```

## MinIO Requirements

### Bucket Configuration

```yaml
Bucket: crawl-results
Access: Read access for Analytics Service
```

### File Format

- **Format:** JSON (array hoặc object)
- **Compression:** Zstd (recommended, level 2)
- **Encoding:** UTF-8

### Compression Metadata (Required for compressed files)

Khi upload file compressed, Crawler **PHẢI** set metadata:

```yaml
x-amz-meta-compressed: "true"
x-amz-meta-compression-algorithm: "zstd"
x-amz-meta-compression-level: "2"
x-amz-meta-original-size: "102400"
x-amz-meta-compressed-size: "25600"
```

**Important:** Analytics Service detect compression bằng cách check:

1. `x-amz-meta-compressed == "true"` (Crawler format)
2. `x-amz-meta-compression-algorithm == "zstd"` (Analytics format)

### JSON Format Support

Analytics Service hỗ trợ cả 2 format:

**Crawler format (JSON array):**

```json
[
  {"meta": {"id": "post_1"}, "content": {...}},
  {"meta": {"id": "post_2"}, "content": {...}}
]
```

**Analytics format (JSON object with items):**

```json
{
  "items": [
    {"meta": {"id": "post_1"}, "content": {...}},
    {"meta": {"id": "post_2"}, "content": {...}}
  ],
  "count": 2
}
```

**Recommendation:** Crawler nên sử dụng JSON array format để giảm overhead.

### Retention Policy

- Batch files **SHOULD** be retained for at least 7 days
- Analytics Service không delete files sau khi xử lý

## Database Requirements (For Consumers)

### post_analytics Table

Consumers của analytics data cần aware các fields mới:

| Field              | Type         | Description                          |
| ------------------ | ------------ | ------------------------------------ |
| `job_id`           | VARCHAR(100) | Crawler job identifier               |
| `batch_index`      | INTEGER      | Batch sequence number                |
| `task_type`        | VARCHAR(30)  | Task type (research_and_crawl, etc.) |
| `keyword_source`   | VARCHAR(200) | Search keyword used                  |
| `crawled_at`       | TIMESTAMP    | When content was crawled             |
| `pipeline_version` | VARCHAR(50)  | Crawler pipeline version             |
| `fetch_status`     | VARCHAR(10)  | success or error                     |
| `error_code`       | VARCHAR(50)  | Error code if failed                 |

### crawl_errors Table

Error analytics available via:

```sql
SELECT
    error_code,
    error_category,
    COUNT(*) as count
FROM crawl_errors
WHERE project_id = ?
GROUP BY error_code, error_category;
```

## Validation Checklist

### For Crawler Services

- [ ] Event schema matches specification
- [ ] Job ID follows correct format
- [ ] MinIO path is valid
- [ ] Batch data is valid JSON array
- [ ] Error items have required fields
- [ ] Error codes are from supported list

### For Downstream Consumers

- [ ] Handle nullable `project_id` (dry-run tasks)
- [ ] Handle new fields in `post_analytics`
- [ ] Query `crawl_errors` for error analytics

## Versioning

| Version | Date       | Changes                                                      |
| ------- | ---------- | ------------------------------------------------------------ |
| 1.0     | 2025-12-06 | Initial contract                                             |
| 1.1     | 2025-12-07 | Added compression metadata requirements, JSON format support |

## Contact

For integration questions, contact Analytics Team.
