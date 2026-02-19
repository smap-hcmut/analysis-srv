# Input Payload — SMAP Analysis Service

## Tổng quan

Analysis Service nhận message từ Kafka topic `smap.collector.output`. Message body là JSON UTF-8 theo format **UAP v1.0 (Unified Analytics Protocol)** — chuẩn dữ liệu thống nhất cho toàn bộ hệ thống SMAP.

**UAP** là format chuẩn hóa để mọi nguồn dữ liệu (Social Crawl, File Upload, Webhook) đều được chuyển đổi về cùng một cấu trúc trước khi đẩy vào Analytics pipeline.

---

## Cấu trúc UAP v1.0

Một UAP Record gồm 6 khối chính:

```jsonc
{
  "uap_version": "1.0",           // Phiên bản format
  "event_id": "uuid",             // ID duy nhất của message
  "ingest": { ... },              // Metadata thu thập
  "content": { ... },             // Nội dung chính cần phân tích
  "signals": { ... },             // Metrics (like, share, view)
  "context": { ... },             // Ngữ cảnh bổ sung
  "raw": { ... }                  // Dữ liệu gốc (debug)
}
```

---

## Chi tiết từng Block

### 1. Root Fields

| Field         | Type   | Required | Description                          |
| :------------ | :----- | :------- | :----------------------------------- |
| `uap_version` | String | ✅       | Phiên bản schema (hiện tại: `"1.0"`) |
| `event_id`    | UUID   | ✅       | ID duy nhất của message trong queue  |

### 2. Block: `ingest` (Metadata thu thập)

Chứa thông tin về nguồn gốc và quản trị dữ liệu.

| Field                | Type    | Required | Description                                                            |
| :------------------- | :------ | :------- | :--------------------------------------------------------------------- |
| `project_id`         | String  | ✅       | ID của Project sở hữu dữ liệu (quan trọng cho phân quyền/billing)      |
| **`entity`**         | Object  | ✅       | Thông tin về thực thể đang theo dõi                                    |
| `entity.entity_type` | Enum    | ✅       | Loại: `product`, `campaign`, `service`, `competitor`, `topic`          |
| `entity.entity_name` | String  | ✅       | Tên cụ thể (VD: "VF8", "iPhone 15")                                    |
| `entity.brand`       | String  | ⚪       | Thương hiệu (VD: "VinFast")                                            |
| **`source`**         | Object  | ✅       | Nguồn gốc dữ liệu                                                      |
| `source.source_id`   | String  | ✅       | ID cấu hình source trong DB                                            |
| `source.source_type` | Enum    | ✅       | `FACEBOOK`, `TIKTOK`, `YOUTUBE`, `INSTAGRAM`, `FILE_UPLOAD`, `WEBHOOK` |
| `source.account_ref` | Object  | ⚪       | Tham chiếu tài khoản/file gốc                                          |
| **`batch`**          | Object  | ✅       | Thông tin đợt thu thập                                                 |
| `batch.batch_id`     | String  | ✅       | ID của batch                                                           |
| `batch.mode`         | Enum    | ✅       | `SCHEDULED_CRAWL`, `MANUAL_UPLOAD`, `WEBHOOK`                          |
| `batch.received_at`  | ISO8601 | ✅       | Thời điểm hệ thống nhận dữ liệu                                        |
| **`trace`**          | Object  | ⚪       | Dùng cho debug/audit                                                   |
| `trace.raw_ref`      | URI     | ⚪       | Đường dẫn file raw gốc (MinIO/S3)                                      |
| `trace.mapping_id`   | String  | ⚪       | ID quy tắc mapping (nếu là File Upload)                                |

**Ví dụ:**

```json
"ingest": {
  "project_id": "proj_vf8_monitor_01",
  "entity": {
    "entity_type": "product",
    "entity_name": "VF8",
    "brand": "VinFast"
  },
  "source": {
    "source_id": "src_fb_01",
    "source_type": "FACEBOOK",
    "account_ref": {
      "name": "VinFast Vietnam",
      "id": "1234567890"
    }
  },
  "batch": {
    "batch_id": "batch_2026_02_07_001",
    "mode": "SCHEDULED_CRAWL",
    "received_at": "2026-02-07T10:00:00Z"
  },
  "trace": {
    "raw_ref": "minio://raw/proj_vf8_monitor_01/facebook/2026-02-07/batch_001.jsonl",
    "mapping_id": "map_fb_default_v3"
  }
}
```

### 3. Block: `content` (Nội dung chính - AI Input)

Đây là phần quan trọng nhất cho Analytics pipeline (Sentiment, Aspect, Keyword extraction).

| Field                   | Type    | Required | Description                                                    |
| :---------------------- | :------ | :------- | :------------------------------------------------------------- |
| `doc_id`                | String  | ✅       | ID gốc của bài viết bên nền tảng nguồn                         |
| `doc_type`              | String  | ✅       | Loại: `post`, `comment`, `video`, `news`, `feedback`, `review` |
| **`parent`**            | Object  | ⚪       | Nếu là comment, thuộc bài post nào?                            |
| `parent.parent_id`      | String  | ⚪       | ID của parent                                                  |
| `parent.parent_type`    | String  | ⚪       | Loại của parent                                                |
| `url`                   | URL     | ⚪       | Link trực tiếp đến bài viết gốc                                |
| `language`              | Code    | ⚪       | Mã ngôn ngữ (`vi`, `en`)                                       |
| `published_at`          | ISO8601 | ✅       | Thời điểm nội dung được tạo bởi tác giả                        |
| **`author`**            | Object  | ✅       | Người tạo nội dung                                             |
| `author.author_id`      | String  | ⚪       | ID người dùng bên nguồn                                        |
| `author.display_name`   | String  | ✅       | Tên hiển thị                                                   |
| `author.author_type`    | String  | ⚪       | Loại: `user`, `page`, `bot`                                    |
| `text`                  | String  | ✅       | **DỮ LIỆU CHÍNH:** Văn bản cần phân tích                       |
| **`attachments`**       | Array   | ⚪       | Danh sách ảnh/video đính kèm                                   |
| `attachments[].type`    | Enum    | ✅       | `image`, `video`, `link`                                       |
| `attachments[].url`     | URL     | ⚪       | URL của attachment                                             |
| `attachments[].content` | String  | ⚪       | Mô tả nội dung (OCR text hoặc Caption)                         |

**Ví dụ:**

```json
"content": {
  "doc_id": "fb_post_987654321",
  "doc_type": "post",
  "parent": {
    "parent_id": null,
    "parent_type": null
  },
  "url": "https://facebook.com/.../posts/987654321",
  "language": "vi",
  "published_at": "2026-02-07T09:55:00Z",
  "author": {
    "author_id": "fb_user_abc",
    "display_name": "Nguyễn A",
    "author_type": "user"
  },
  "text": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
  "attachments": [
    {
      "type": "image",
      "url": "https://...",
      "content": "hình ảnh về giá ô tô"
    }
  ]
}
```

### 4. Block: `signals` (Metrics - Tín hiệu số)

Các chỉ số tương tác và đánh giá, dùng cho Impact Calculation.

| Field                      | Type   | Required | Description                         |
| :------------------------- | :----- | :------- | :---------------------------------- |
| **`engagement`**           | Object | ✅       | Các chỉ số tương tác                |
| `engagement.like_count`    | Int    | ⚪       | Số lượt thích/reaction (default: 0) |
| `engagement.comment_count` | Int    | ⚪       | Số lượt bình luận (default: 0)      |
| `engagement.share_count`   | Int    | ⚪       | Số lượt chia sẻ (default: 0)        |
| `engagement.view_count`    | Int    | ⚪       | Số lượt xem (default: 0)            |
| `engagement.rating`        | Float  | ⚪       | Điểm đánh giá (1-5) nếu là Review   |
| **`geo`**                  | Object | ⚪       | Thông tin địa lý                    |
| `geo.country`              | String | ⚪       | Mã quốc gia (VD: "VN")              |
| `geo.city`                 | String | ⚪       | Thành phố                           |

**Ví dụ:**

```json
"signals": {
  "engagement": {
    "like_count": 120,
    "comment_count": 34,
    "share_count": 5,
    "view_count": 1111,
    "rating": null
  },
  "geo": {
    "country": "VN",
    "city": null
  }
}
```

### 5. Block: `context` (Ngữ cảnh bổ sung)

Thông tin được làm giàu (enriched) ngay từ lúc Ingest.

| Field              | Type   | Required | Description                                     |
| :----------------- | :----- | :------- | :---------------------------------------------- |
| `keywords_matched` | Array  | ⚪       | Bài viết match với từ khóa monitoring nào?      |
| `campaign_id`      | String | ⚪       | ID chiến dịch (nếu thuộc chiến dịch đang track) |

**Ví dụ:**

```json
"context": {
  "keywords_matched": ["vf8", "pin", "giá"],
  "campaign_id": "id_feb_campaign_2026_01"
}
```

### 6. Block: `raw` (Dữ liệu gốc)

Dữ liệu thô chưa qua xử lý, dùng để đối chiếu khi cần debug.

```json
"raw": {
  "original_fields": {
    "post_id": "987654321",
    "author_name": "Nguyễn A",
    "content": "Xe đi êm nhưng pin sụt nhanh...",
    "like": 120,
    "comment": 34
  }
}
```

---

## Ví dụ UAP Record đầy đủ

### Example 1: Facebook Post (Crawl)

```json
{
  "uap_version": "1.0",
  "event_id": "b6d6b1e2-9cf3-4e69-8fd0-5b1c8aab9f17",
  "ingest": {
    "project_id": "proj_vf8_monitor_01",
    "entity": {
      "entity_type": "product",
      "entity_name": "VF8",
      "brand": "VinFast"
    },
    "source": {
      "source_id": "src_fb_01",
      "source_type": "FACEBOOK",
      "account_ref": {
        "name": "VinFast Vietnam",
        "id": "1234567890"
      }
    },
    "batch": {
      "batch_id": "batch_2026_02_07_001",
      "mode": "SCHEDULED_CRAWL",
      "received_at": "2026-02-07T10:00:00Z"
    },
    "trace": {
      "raw_ref": "minio://raw/proj_vf8_monitor_01/facebook/2026-02-07/batch_001.jsonl",
      "mapping_id": "map_fb_default_v3"
    }
  },
  "content": {
    "doc_id": "fb_post_987654321",
    "doc_type": "post",
    "parent": null,
    "url": "https://facebook.com/.../posts/987654321",
    "language": "vi",
    "published_at": "2026-02-07T09:55:00Z",
    "author": {
      "author_id": "fb_user_abc",
      "display_name": "Nguyễn A",
      "author_type": "user"
    },
    "text": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
    "attachments": [
      {
        "type": "image",
        "url": "https://...",
        "content": "hình ảnh về giá ô tô"
      }
    ]
  },
  "signals": {
    "engagement": {
      "like_count": 120,
      "comment_count": 34,
      "share_count": 5,
      "view_count": 1111,
      "rating": null
    },
    "geo": {
      "country": "VN",
      "city": null
    }
  },
  "context": {
    "keywords_matched": ["vf8", "pin", "giá"],
    "campaign_id": "id_feb_campaign_2026_01"
  },
  "raw": {
    "original_fields": {
      "post_id": "987654321",
      "author_name": "Nguyễn A",
      "content": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
      "like": 120,
      "comment": 34,
      "share": 5,
      "view": 1111,
      "created_time": "2026-02-07T09:55:00Z"
    }
  }
}
```

### Example 2: CSV Upload (Manual)

```json
{
  "uap_version": "1.0",
  "event_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "ingest": {
    "project_id": "proj_customer_feedback_q1",
    "entity": {
      "entity_type": "service",
      "entity_name": "Customer Support",
      "brand": "ACME Corp"
    },
    "source": {
      "source_id": "src_csv_upload_001",
      "source_type": "FILE_UPLOAD",
      "account_ref": {
        "filename": "feedback_jan_2026.csv",
        "uploaded_by": "user_admin_01"
      }
    },
    "batch": {
      "batch_id": "batch_csv_2026_01_15",
      "mode": "MANUAL_UPLOAD",
      "received_at": "2026-01-15T14:30:00Z"
    },
    "trace": {
      "raw_ref": "minio://uploads/proj_customer_feedback_q1/feedback_jan_2026.csv",
      "mapping_id": "map_csv_feedback_v2"
    }
  },
  "content": {
    "doc_id": "csv_row_42",
    "doc_type": "feedback",
    "parent": null,
    "url": null,
    "language": "vi",
    "published_at": "2026-01-10T08:00:00Z",
    "author": {
      "author_id": "customer_12345",
      "display_name": "Khách hàng #12345",
      "author_type": "user"
    },
    "text": "Dịch vụ chăm sóc khách hàng rất tốt, nhân viên nhiệt tình.",
    "attachments": []
  },
  "signals": {
    "engagement": {
      "like_count": 0,
      "comment_count": 0,
      "share_count": 0,
      "view_count": 0,
      "rating": 5.0
    },
    "geo": {
      "country": "VN",
      "city": "Ho Chi Minh"
    }
  },
  "context": {
    "keywords_matched": ["dịch vụ", "chăm sóc"],
    "campaign_id": null
  },
  "raw": {
    "csv_row": {
      "row_number": 42,
      "customer_id": "12345",
      "feedback_text": "Dịch vụ chăm sóc khách hàng rất tốt, nhân viên nhiệt tình.",
      "rating": "5",
      "date": "2026-01-10"
    }
  }
}
```

---

## Validation Rules

Analysis Service sẽ validate UAP message theo các quy tắc sau:

### Required Fields

- `uap_version` phải là `"1.0"`
- `event_id` phải là UUID hợp lệ
- `ingest.project_id` không được rỗng
- `ingest.entity.entity_type` phải thuộc enum hợp lệ
- `ingest.source.source_type` phải thuộc enum hợp lệ
- `content.doc_id` không được rỗng
- `content.text` không được rỗng (hoặc có attachments với content)
- `content.published_at` phải là ISO8601 hợp lệ

### Optional but Recommended

- `content.author.display_name` - cần cho author attribution
- `signals.engagement.*` - cần cho Impact Calculation
- `context.keywords_matched` - cần cho keyword tracking

### Error Handling

- Nếu `uap_version` không phải `"1.0"` → Reject message
- Nếu thiếu required fields → Reject message
- Nếu `content.text` rỗng và không có attachments → Skip processing
- Nếu `published_at` invalid → Sử dụng `batch.received_at` thay thế

---

## Queue Configuration

**Kafka Setup:**

```yaml
kafka:
  bootstrap_servers: "172.16.21.206:9092"

  consumer:
    group_id: "analytics-service"
    topics:
      - "smap.collector.output"
    auto_offset_reset: "earliest"
    enable_auto_commit: false
    max_poll_records: 10
```

**Message Properties:**

- Content-Type: `application/json`
- Encoding: `UTF-8`
- Key: `project_id` (for partitioning)

---

## Migration from Event Envelope

**Legacy format (REMOVED):**

- Broker: RabbitMQ
- Queue: `analytics.data.collected`
- Format: Event Envelope (flat structure)

**Current format (UAP v1.0):**

- Broker: Kafka
- Topic: `smap.collector.output`
- Format: UAP (nested, structured)

**Key differences:**

- Kafka instead of RabbitMQ for better scalability
- UAP có nested structure rõ ràng hơn
- UAP có `entity` context cho AI model selection
- UAP có `trace` block cho audit trail
- UAP có `attachments` support cho multimodal analysis

---

## References

- **UAP Specification**: `refactor_plan/input-output/input/UAP_INPUT_SCHEMA.md`
- **More Examples**: `refactor_plan/input-output/input/example_input_*.json`
- **Output Format**: `documents/output_payload.md`
- **Master Proposal**: `documents/master-proposal.md`
