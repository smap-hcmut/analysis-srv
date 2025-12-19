# Analytics API Design Proposal

## Overview

Thiết kế REST API cho Analytics Service để phục vụ Dashboard hiển thị dữ liệu phân tích bài viết mạng xã hội.

**Scope:** Read-only APIs để query dữ liệu đã phân tích.

**Base URL:** `/api/v1/analytics`

**Filter chính:** Tất cả APIs đều filter theo:

- `project_id` (UUID) - **Required**
- `brand_name` (string) - Optional
- `keyword` (string) - Optional

---

## Data Flow

```
User tạo Project
  → Nhập nhiều Brands (thương hiệu)
    → Mỗi Brand có nhiều Keywords
      → Crawler crawl theo keywords
        → Analytics phân tích + lưu DB
          → API serve data → Dashboard
```

**Note:** Analytics service không quản lý hierarchy Project/Brand/Keyword. Chỉ nhận và lưu `project_id`, `brand_name`, `keyword` như metadata từ Crawler events.

---

## Response Format Standards

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

### Pagination Response

```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "VAL_001",
    "message": "Validation failed",
    "details": [
      {
        "field": "project_id",
        "message": "project_id is required",
        "code": "REQUIRED_FIELD"
      }
    ]
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

---

## Error Codes

### HTTP Status Codes

| Status | Usage                                       |
| ------ | ------------------------------------------- |
| `200`  | Success - GET requests                      |
| `400`  | Bad Request - Input validation failed       |
| `404`  | Not Found - Resource không tồn tại          |
| `422`  | Unprocessable Entity - Business logic error |
| `500`  | Internal Server Error - Unexpected error    |

### Application Error Codes

| Code      | Description            |
| --------- | ---------------------- |
| `VAL_001` | Validation error       |
| `VAL_002` | Invalid format         |
| `VAL_003` | Required field missing |
| `VAL_004` | Invalid range          |
| `RES_001` | Resource not found     |
| `SYS_001` | Internal error         |

---

## API Endpoints

### 1. GET /posts - Danh sách bài viết

Lấy danh sách bài viết đã phân tích với pagination và filters.

#### Request

```
GET /api/v1/analytics/posts?project_id=uuid&brand_name=Samsung&keyword=Galaxy
```

#### Query Parameters

| Param        | Type     | Required | Default     | Description                                                              |
| ------------ | -------- | -------- | ----------- | ------------------------------------------------------------------------ |
| `project_id` | UUID     | ✅ Yes   | -           | Filter theo project                                                      |
| `brand_name` | string   | No       | -           | Filter theo brand                                                        |
| `keyword`    | string   | No       | -           | Filter theo keyword crawl                                                |
| `platform`   | string   | No       | -           | tiktok, facebook, youtube                                                |
| `sentiment`  | string   | No       | -           | POSITIVE, NEGATIVE, NEUTRAL                                              |
| `risk_level` | string   | No       | -           | CRITICAL, HIGH, MEDIUM, LOW                                              |
| `intent`     | string   | No       | -           | CRISIS, COMPLAINT, LEAD, DISCUSSION, SUPPORT, SPAM, SEEDING              |
| `is_viral`   | boolean  | No       | -           | Filter bài viral                                                         |
| `is_kol`     | boolean  | No       | -           | Filter bài từ KOL                                                        |
| `from_date`  | datetime | No       | -           | Filter từ ngày (published_at)                                            |
| `to_date`    | datetime | No       | -           | Filter đến ngày (published_at)                                           |
| `sort_by`    | string   | No       | analyzed_at | Columns: analyzed_at, published_at, impact_score, view_count, like_count |
| `sort_order` | string   | No       | desc        | asc, desc                                                                |
| `page`       | int      | No       | 1           | Trang hiện tại                                                           |
| `page_size`  | int      | No       | 20          | Số items/trang (max 100)                                                 |

#### Response 200

```json
{
  "success": true,
  "data": [
    {
      "id": "tiktok_7441234567890",
      "platform": "tiktok",
      "permalink": "https://www.tiktok.com/@user/video/7441234567890",

      "content_text": "Review Galaxy S24 Ultra sau 1 tháng sử dụng...",

      "author_name": "Tech Reviewer VN",
      "author_username": "@techreviewervn",
      "author_is_verified": true,

      "overall_sentiment": "POSITIVE",
      "overall_sentiment_score": 0.75,
      "primary_intent": "DISCUSSION",
      "impact_score": 82.5,
      "risk_level": "LOW",
      "is_viral": true,
      "is_kol": true,

      "view_count": 500000,
      "like_count": 25000,
      "comment_count": 1200,

      "published_at": "2025-12-15T10:00:00Z",
      "analyzed_at": "2025-12-15T10:05:32Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 1250,
    "total_pages": 63,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

#### Response Fields (List View)

| Field                     | Type     | Description                            |
| ------------------------- | -------- | -------------------------------------- |
| `id`                      | string   | Post ID từ platform                    |
| `platform`                | string   | tiktok, facebook, youtube              |
| `permalink`               | string   | Link đến bài gốc                       |
| `content_text`            | string   | Nội dung bài viết (truncate 300 chars) |
| `author_name`             | string   | Tên tác giả                            |
| `author_username`         | string   | Username tác giả                       |
| `author_is_verified`      | boolean  | Tài khoản verified                     |
| `overall_sentiment`       | string   | POSITIVE, NEGATIVE, NEUTRAL            |
| `overall_sentiment_score` | float    | -1.0 đến 1.0                           |
| `primary_intent`          | string   | Intent chính của bài                   |
| `impact_score`            | float    | 0-100                                  |
| `risk_level`              | string   | CRITICAL, HIGH, MEDIUM, LOW            |
| `is_viral`                | boolean  | Bài viral (impact >= 70)               |
| `is_kol`                  | boolean  | Từ KOL (followers >= 50k)              |
| `view_count`              | int      | Lượt xem                               |
| `like_count`              | int      | Lượt thích                             |
| `comment_count`           | int      | Số comments                            |
| `published_at`            | datetime | Thời gian đăng bài                     |
| `analyzed_at`             | datetime | Thời gian phân tích                    |

**Không bao gồm trong list view:** `aspects_breakdown`, `keywords`, `impact_breakdown`, `sentiment_probabilities`, `comments`, `hashtags`, `content_transcription`, `share_count`, `save_count`, `author_avatar_url`

---

### 1.1 GET /posts/all - Danh sách bài viết (không pagination)

Lấy tất cả bài viết theo filters, không có pagination. Dùng cho export hoặc khi cần full data.

**⚠️ Warning:** API này có thể trả về lượng data lớn. Nên giới hạn bằng `limit` hoặc date range.

#### Request

```
GET /api/v1/analytics/posts/all?project_id=uuid&brand_name=Samsung&keyword=Galaxy&limit=1000
```

#### Query Parameters

| Param        | Type     | Required | Default     | Description                                                              |
| ------------ | -------- | -------- | ----------- | ------------------------------------------------------------------------ |
| `project_id` | UUID     | ✅ Yes   | -           | Filter theo project                                                      |
| `brand_name` | string   | No       | -           | Filter theo brand                                                        |
| `keyword`    | string   | No       | -           | Filter theo keyword crawl                                                |
| `platform`   | string   | No       | -           | tiktok, facebook, youtube                                                |
| `sentiment`  | string   | No       | -           | POSITIVE, NEGATIVE, NEUTRAL                                              |
| `risk_level` | string   | No       | -           | CRITICAL, HIGH, MEDIUM, LOW                                              |
| `intent`     | string   | No       | -           | CRISIS, COMPLAINT, LEAD, DISCUSSION, SUPPORT, SPAM, SEEDING              |
| `is_viral`   | boolean  | No       | -           | Filter bài viral                                                         |
| `is_kol`     | boolean  | No       | -           | Filter bài từ KOL                                                        |
| `from_date`  | datetime | No       | -           | Filter từ ngày (published_at)                                            |
| `to_date`    | datetime | No       | -           | Filter đến ngày (published_at)                                           |
| `sort_by`    | string   | No       | analyzed_at | Columns: analyzed_at, published_at, impact_score, view_count, like_count |
| `sort_order` | string   | No       | desc        | asc, desc                                                                |
| `limit`      | int      | No       | 1000        | Giới hạn số records (max 10000)                                          |

#### Response 200

```json
{
  "success": true,
  "data": [
    {
      "id": "tiktok_7441234567890",
      "platform": "tiktok",
      "permalink": "https://www.tiktok.com/@user/video/7441234567890",

      "content_text": "Review Galaxy S24 Ultra sau 1 tháng sử dụng...",

      "author_name": "Tech Reviewer VN",
      "author_username": "@techreviewervn",
      "author_is_verified": true,

      "overall_sentiment": "POSITIVE",
      "overall_sentiment_score": 0.75,
      "primary_intent": "DISCUSSION",
      "impact_score": 82.5,
      "risk_level": "LOW",
      "is_viral": true,
      "is_kol": true,

      "view_count": 500000,
      "like_count": 25000,
      "comment_count": 1200,

      "published_at": "2025-12-15T10:00:00Z",
      "analyzed_at": "2025-12-15T10:05:32Z"
    }
  ],
  "total": 1250,
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

**Note:** Response không có `pagination` object, chỉ có `total` để biết tổng số records.

---

### 2. GET /posts/{post_id} - Chi tiết bài viết

Lấy full thông tin của 1 bài viết bao gồm analysis details và comments.

#### Request

```
GET /api/v1/analytics/posts/tiktok_7441234567890
```

#### Response 200

```json
{
  "success": true,
  "data": {
    "id": "tiktok_7441234567890",
    "platform": "tiktok",
    "permalink": "https://www.tiktok.com/@user/video/7441234567890",

    "content_text": "Review Galaxy S24 Ultra sau 1 tháng sử dụng. Màn hình đẹp, camera chụp đêm xuất sắc nhưng giá hơi cao...",
    "content_transcription": "Xin chào các bạn, hôm nay mình sẽ review...",
    "hashtags": ["#samsung", "#galaxys24", "#review", "#tech"],
    "media_duration": 180,

    "author_id": "user123456",
    "author_name": "Tech Reviewer VN",
    "author_username": "@techreviewervn",
    "author_avatar_url": "https://p16-sign.tiktokcdn.com/...",
    "author_is_verified": true,
    "follower_count": 150000,

    "overall_sentiment": "POSITIVE",
    "overall_sentiment_score": 0.75,
    "overall_confidence": 0.92,
    "sentiment_probabilities": {
      "POSITIVE": 0.82,
      "NEUTRAL": 0.12,
      "NEGATIVE": 0.06
    },

    "primary_intent": "DISCUSSION",
    "intent_confidence": 0.88,

    "impact_score": 82.5,
    "risk_level": "LOW",
    "is_viral": true,
    "is_kol": true,
    "impact_breakdown": {
      "engagement_score": 45.2,
      "reach_score": 5.18,
      "platform_multiplier": 1.2,
      "sentiment_amplifier": 1.0,
      "raw_impact": 280.5
    },

    "aspects_breakdown": {
      "DESIGN": {
        "sentiment": "POSITIVE",
        "score": 0.85,
        "confidence": 0.9,
        "keywords": ["màn hình", "đẹp", "thiết kế"]
      },
      "PERFORMANCE": {
        "sentiment": "POSITIVE",
        "score": 0.72,
        "confidence": 0.85,
        "keywords": ["camera", "chụp đêm", "xuất sắc"]
      },
      "PRICE": {
        "sentiment": "NEGATIVE",
        "score": -0.45,
        "confidence": 0.78,
        "keywords": ["giá", "cao", "đắt"]
      }
    },

    "keywords": [
      {
        "keyword": "màn hình",
        "aspect": "DESIGN",
        "sentiment": "POSITIVE",
        "score": 0.85
      },
      {
        "keyword": "camera",
        "aspect": "PERFORMANCE",
        "sentiment": "POSITIVE",
        "score": 0.72
      },
      {
        "keyword": "giá",
        "aspect": "PRICE",
        "sentiment": "NEGATIVE",
        "score": -0.45
      }
    ],

    "view_count": 500000,
    "like_count": 25000,
    "comment_count": 1200,
    "share_count": 3500,
    "save_count": 8000,

    "published_at": "2025-12-15T10:00:00Z",
    "analyzed_at": "2025-12-15T10:05:32Z",
    "crawled_at": "2025-12-15T10:03:00Z",

    "brand_name": "Samsung",
    "keyword": "Galaxy S24",
    "job_id": "proj123-samsung-0",

    "comments": [
      {
        "id": 1,
        "comment_id": "cmt_123456",
        "text": "Máy đẹp quá, đang định mua!",
        "author_name": "user_abc",
        "likes": 150,
        "sentiment": "POSITIVE",
        "sentiment_score": 0.88,
        "commented_at": "2025-12-15T11:30:00Z"
      }
    ],
    "comments_total": 1200
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

#### Response 404

```json
{
  "success": false,
  "error": {
    "code": "RES_001",
    "message": "Post with id 'tiktok_notexist' not found",
    "details": []
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

---

### 3. GET /summary - Thống kê tổng hợp

Dashboard overview cho project/brand/keyword.

#### Request

```
GET /api/v1/analytics/summary?project_id=uuid&brand_name=Samsung&from_date=2025-12-01&to_date=2025-12-19
```

#### Query Parameters

| Param        | Type     | Required | Description         |
| ------------ | -------- | -------- | ------------------- |
| `project_id` | UUID     | ✅ Yes   | Filter theo project |
| `brand_name` | string   | No       | Filter theo brand   |
| `keyword`    | string   | No       | Filter theo keyword |
| `from_date`  | datetime | No       | Từ ngày             |
| `to_date`    | datetime | No       | Đến ngày            |

#### Response 200

```json
{
  "success": true,
  "data": {
    "total_posts": 1250,
    "total_comments": 15000,

    "sentiment_distribution": {
      "POSITIVE": 520,
      "NEUTRAL": 480,
      "NEGATIVE": 250
    },
    "avg_sentiment_score": 0.35,

    "risk_distribution": {
      "CRITICAL": 15,
      "HIGH": 85,
      "MEDIUM": 350,
      "LOW": 800
    },

    "intent_distribution": {
      "DISCUSSION": 600,
      "COMPLAINT": 200,
      "LEAD": 150,
      "CRISIS": 20,
      "SUPPORT": 100,
      "SPAM": 80,
      "SEEDING": 100
    },

    "platform_distribution": {
      "tiktok": 800,
      "facebook": 300,
      "youtube": 150
    },

    "engagement_totals": {
      "views": 25000000,
      "likes": 500000,
      "comments": 15000,
      "shares": 8000,
      "saves": 12000
    },

    "viral_count": 45,
    "kol_count": 120,
    "avg_impact_score": 42.5
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

---

### 4. GET /trends - Xu hướng theo thời gian

Data cho line/bar charts trên dashboard.

#### Request

```
GET /api/v1/analytics/trends?project_id=uuid&brand_name=Samsung&granularity=day&from_date=2025-12-01&to_date=2025-12-19
```

#### Query Parameters

| Param         | Type     | Required | Default | Description         |
| ------------- | -------- | -------- | ------- | ------------------- |
| `project_id`  | UUID     | ✅ Yes   | -       | Filter theo project |
| `brand_name`  | string   | No       | -       | Filter theo brand   |
| `keyword`     | string   | No       | -       | Filter theo keyword |
| `granularity` | string   | No       | day     | day, week, month    |
| `from_date`   | datetime | ✅ Yes   | -       | Từ ngày             |
| `to_date`     | datetime | ✅ Yes   | -       | Đến ngày            |

#### Response 200

```json
{
  "success": true,
  "data": {
    "granularity": "day",
    "items": [
      {
        "date": "2025-12-15",
        "post_count": 45,
        "comment_count": 520,
        "avg_sentiment_score": 0.42,
        "avg_impact_score": 38.5,
        "sentiment_breakdown": {
          "POSITIVE": 20,
          "NEUTRAL": 15,
          "NEGATIVE": 10
        },
        "total_views": 1500000,
        "total_likes": 45000,
        "viral_count": 3,
        "crisis_count": 1
      },
      {
        "date": "2025-12-16",
        "post_count": 52,
        "comment_count": 610,
        "avg_sentiment_score": 0.38,
        "avg_impact_score": 41.2,
        "sentiment_breakdown": {
          "POSITIVE": 22,
          "NEUTRAL": 18,
          "NEGATIVE": 12
        },
        "total_views": 1800000,
        "total_likes": 52000,
        "viral_count": 4,
        "crisis_count": 0
      }
    ]
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

---

### 5. GET /top-keywords - Top keywords

Keywords xuất hiện nhiều nhất với sentiment.

#### Request

```
GET /api/v1/analytics/top-keywords?project_id=uuid&brand_name=Samsung&limit=20
```

#### Query Parameters

| Param        | Type     | Required | Default | Description                 |
| ------------ | -------- | -------- | ------- | --------------------------- |
| `project_id` | UUID     | ✅ Yes   | -       | Filter theo project         |
| `brand_name` | string   | No       | -       | Filter theo brand           |
| `keyword`    | string   | No       | -       | Filter theo keyword         |
| `from_date`  | datetime | No       | -       | Từ ngày                     |
| `to_date`    | datetime | No       | -       | Đến ngày                    |
| `limit`      | int      | No       | 20      | Số keywords trả về (max 50) |

#### Response 200

```json
{
  "success": true,
  "data": {
    "keywords": [
      {
        "keyword": "màn hình",
        "count": 350,
        "avg_sentiment_score": 0.65,
        "aspect": "DESIGN",
        "sentiment_breakdown": {
          "POSITIVE": 280,
          "NEUTRAL": 50,
          "NEGATIVE": 20
        }
      },
      {
        "keyword": "giá",
        "count": 280,
        "avg_sentiment_score": -0.15,
        "aspect": "PRICE",
        "sentiment_breakdown": {
          "POSITIVE": 80,
          "NEUTRAL": 100,
          "NEGATIVE": 100
        }
      },
      {
        "keyword": "camera",
        "count": 220,
        "avg_sentiment_score": 0.72,
        "aspect": "PERFORMANCE",
        "sentiment_breakdown": {
          "POSITIVE": 180,
          "NEUTRAL": 30,
          "NEGATIVE": 10
        }
      }
    ]
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

**Implementation Note:** `keywords` được lưu dạng JSONB trong `post_analytics`. Cần sử dụng PostgreSQL JSONB functions hoặc aggregate ở application layer.

---

### 6. GET /alerts - Bài cần chú ý

Posts có risk cao, viral, hoặc crisis intent.

#### Request

```
GET /api/v1/analytics/alerts?project_id=uuid&brand_name=Samsung&limit=10
```

#### Query Parameters

| Param        | Type   | Required | Default | Description           |
| ------------ | ------ | -------- | ------- | --------------------- |
| `project_id` | UUID   | ✅ Yes   | -       | Filter theo project   |
| `brand_name` | string | No       | -       | Filter theo brand     |
| `keyword`    | string | No       | -       | Filter theo keyword   |
| `limit`      | int    | No       | 10      | Số items mỗi category |

#### Response 200

```json
{
  "success": true,
  "data": {
    "critical_posts": [
      {
        "id": "tiktok_999",
        "content_text": "Samsung bị tố lừa đảo khách hàng...",
        "risk_level": "CRITICAL",
        "impact_score": 95.2,
        "overall_sentiment": "NEGATIVE",
        "view_count": 2000000,
        "published_at": "2025-12-18T08:00:00Z",
        "permalink": "https://..."
      }
    ],
    "viral_posts": [
      {
        "id": "tiktok_888",
        "content_text": "Unbox Galaxy S24 siêu đẹp...",
        "is_viral": true,
        "impact_score": 88.5,
        "overall_sentiment": "POSITIVE",
        "view_count": 5000000,
        "published_at": "2025-12-17T14:00:00Z",
        "permalink": "https://..."
      }
    ],
    "crisis_intents": [
      {
        "id": "facebook_777",
        "content_text": "Điện thoại phát nổ khi sạc...",
        "primary_intent": "CRISIS",
        "risk_level": "HIGH",
        "impact_score": 72.0,
        "overall_sentiment": "NEGATIVE",
        "view_count": 150000,
        "published_at": "2025-12-16T20:00:00Z",
        "permalink": "https://..."
      }
    ],
    "summary": {
      "critical_count": 5,
      "viral_count": 12,
      "crisis_count": 3
    }
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

---

### 7. GET /errors - Crawl errors

Tracking lỗi từ Crawler.

#### Request

```
GET /api/v1/analytics/errors?project_id=uuid&job_id=proj123-samsung-0
```

#### Query Parameters

| Param        | Type     | Required | Description              |
| ------------ | -------- | -------- | ------------------------ |
| `project_id` | UUID     | ✅ Yes   | Filter theo project      |
| `job_id`     | string   | No       | Filter theo job          |
| `error_code` | string   | No       | Filter theo error code   |
| `from_date`  | datetime | No       | Từ ngày                  |
| `to_date`    | datetime | No       | Đến ngày                 |
| `page`       | int      | No       | Trang (default 1)        |
| `page_size`  | int      | No       | Items/trang (default 20) |

#### Response 200

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "content_id": "tiktok_deleted_123",
      "platform": "tiktok",
      "error_code": "CONTENT_DELETED",
      "error_category": "NOT_FOUND",
      "error_message": "Video has been removed by the creator",
      "permalink": "https://www.tiktok.com/@user/video/deleted_123",
      "job_id": "proj123-samsung-0",
      "created_at": "2025-12-15T10:00:00Z"
    },
    {
      "id": 2,
      "content_id": "tiktok_private_456",
      "platform": "tiktok",
      "error_code": "CONTENT_PRIVATE",
      "error_category": "ACCESS_DENIED",
      "error_message": "This video is private",
      "permalink": "https://www.tiktok.com/@user/video/private_456",
      "job_id": "proj123-samsung-0",
      "created_at": "2025-12-15T10:01:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 25,
    "total_pages": 2,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

---

## Health Check Endpoints

### GET /health - Basic Health Check

```json
{
  "status": "healthy"
}
```

### GET /health/detailed - Detailed Health Check

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy"
  },
  "uptime": "2d 5h 30m"
}
```

---

## API Documentation (Swagger)

### Endpoints

| Path                  | Description                                |
| --------------------- | ------------------------------------------ |
| `/swagger/index.html` | Swagger UI - Interactive API documentation |
| `/openapi.json`       | OpenAPI 3.0 specification (JSON)           |

### Configuration

```python
# internal/api/main.py
from fastapi import FastAPI

app = FastAPI(
    title="Analytics Engine API",
    description="REST API for querying social media analytics data",
    version="1.0.0",
    docs_url="/swagger/index.html",  # Swagger UI path
    redoc_url=None,                   # Disable ReDoc
    openapi_url="/openapi.json"       # OpenAPI spec path
)
```

### Features

- Interactive API testing từ browser
- Auto-generated từ Pydantic schemas
- Request/Response examples
- Authentication documentation (nếu có)

---

## Database Indexes Required

Để đảm bảo performance cho các queries:

```sql
-- CẦN THÊM
CREATE INDEX idx_post_analytics_project_id ON post_analytics(project_id);

-- Composite indexes cho common queries
CREATE INDEX idx_post_analytics_project_brand ON post_analytics(project_id, brand_name);
CREATE INDEX idx_post_analytics_project_brand_keyword ON post_analytics(project_id, brand_name, keyword);

-- Date range queries
CREATE INDEX idx_post_analytics_published_at ON post_analytics(published_at);
CREATE INDEX idx_post_analytics_analyzed_at ON post_analytics(analyzed_at);
```

---

## Implementation Notes

### 1. Pagination

- Sử dụng offset-based pagination
- Max page_size = 100
- Trả về `has_next`, `has_prev` để UI navigation

### 2. JSONB Queries (top-keywords)

- Option A: PostgreSQL `jsonb_array_elements` + aggregation
- Option B: Load posts, aggregate keywords ở Python
- Recommend: Option A cho production

### 3. Date Filtering

- Filter trên `published_at` cho business queries
- Dùng `from_date`, `to_date` theo convention

### 4. Response Truncation

- `content_text` trong list view: truncate 300 chars
- Full content chỉ trả ở detail view

### 5. Request ID

- Generate UUID cho mỗi request
- Include trong response `meta.request_id`
- Log với request_id để trace

---

## API Summary

| Endpoint           | Method | Description                              |
| ------------------ | ------ | ---------------------------------------- |
| `/posts`           | GET    | List posts với filters + pagination      |
| `/posts/all`       | GET    | List posts không pagination (for export) |
| `/posts/{id}`      | GET    | Chi tiết 1 post + comments               |
| `/summary`         | GET    | Thống kê tổng hợp                        |
| `/trends`          | GET    | Data theo timeline                       |
| `/top-keywords`    | GET    | Top keywords với sentiment               |
| `/alerts`          | GET    | Posts cần chú ý                          |
| `/errors`          | GET    | Crawl errors tracking                    |
| `/health`          | GET    | Basic health check                       |
| `/health/detailed` | GET    | Detailed health check                    |

Tất cả endpoints (trừ health) support filter theo `project_id` (required), `brand_name`, `keyword` (optional).
