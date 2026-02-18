-- ============================================================================
-- SMAP Analysis Service — UAP v1.0 Input Schema (SQL Representation)
-- ============================================================================
-- Mô tả cấu trúc JSON message mà service nhận từ Kafka.
-- Topic: smap.collector.output
-- Consumer Group: analytics-service
-- Format: UAP v1.0 (Unified Analytics Protocol)
--
-- Đây KHÔNG phải table thực tế trong DB, mà là mô tả cấu trúc input
-- dưới dạng SQL-like schema để dễ tham chiếu.
-- ============================================================================

-- ─── UAP Record (root level) ───────────────────────────────────────────────
-- JSON message body gửi qua RabbitMQ theo chuẩn UAP v1.0
CREATE TYPE uap_record AS (
    -- Phiên bản UAP schema. MUST be "1.0"
    uap_version     TEXT,

    -- UUID định danh message trong queue
    event_id        TEXT,

    -- Metadata thu thập
    ingest          uap_ingest,

    -- Nội dung chính cần phân tích
    content         uap_content,

    -- Tín hiệu số (metrics)
    signals         uap_signals,

    -- Ngữ cảnh bổ sung
    context         uap_context,

    -- Dữ liệu gốc (debug)
    raw             JSONB
);

-- ─── Ingest Block ──────────────────────────────────────────────────────────
CREATE TYPE uap_ingest AS (
    -- [REQUIRED] ID của project sở hữu dữ liệu
    project_id      TEXT,

    -- Thông tin về thực thể đang theo dõi
    entity          uap_entity,

    -- Nguồn gốc dữ liệu
    source          uap_source,

    -- Thông tin đợt thu thập
    batch           uap_batch,

    -- Trace cho debug/audit
    trace           uap_trace
);

CREATE TYPE uap_entity AS (
    -- [REQUIRED] Loại thực thể: product, campaign, service, competitor, topic
    entity_type     TEXT,

    -- [REQUIRED] Tên cụ thể (VD: "VF8", "iPhone 15")
    entity_name     TEXT,

    -- Thương hiệu (VD: "VinFast")
    brand           TEXT
);

CREATE TYPE uap_source AS (
    -- [REQUIRED] ID cấu hình source trong DB
    source_id       TEXT,

    -- [REQUIRED] Loại nguồn: FACEBOOK, TIKTOK, YOUTUBE, INSTAGRAM, FILE_UPLOAD, WEBHOOK
    source_type     TEXT,

    -- Tham chiếu tài khoản/file gốc
    account_ref     JSONB
);

CREATE TYPE uap_batch AS (
    -- [REQUIRED] ID của batch
    batch_id        TEXT,

    -- [REQUIRED] Chế độ: SCHEDULED_CRAWL, MANUAL_UPLOAD, WEBHOOK
    mode            TEXT,

    -- [REQUIRED] Thời điểm hệ thống nhận dữ liệu (ISO8601)
    received_at     TEXT
);

CREATE TYPE uap_trace AS (
    -- Đường dẫn file raw gốc (MinIO/S3)
    raw_ref         TEXT,

    -- ID quy tắc mapping (nếu là File Upload)
    mapping_id      TEXT
);

-- ─── Content Block ─────────────────────────────────────────────────────────
CREATE TYPE uap_content AS (
    -- [REQUIRED] ID gốc của bài viết bên nền tảng nguồn
    doc_id          TEXT,

    -- [REQUIRED] Loại nội dung: post, comment, video, news, feedback, review
    doc_type        TEXT,

    -- Nếu là comment, thuộc bài post nào?
    parent          uap_parent,

    -- Link trực tiếp đến bài viết gốc
    url             TEXT,

    -- Mã ngôn ngữ (vi, en)
    language        TEXT,

    -- [REQUIRED] Thời điểm nội dung được tạo bởi tác giả (ISO8601)
    published_at    TEXT,

    -- [REQUIRED] Người tạo nội dung
    author          uap_author,

    -- [REQUIRED] Văn bản cần phân tích
    text            TEXT,

    -- Danh sách ảnh/video đính kèm
    attachments     uap_attachment[]
);

CREATE TYPE uap_parent AS (
    parent_id       TEXT,
    parent_type     TEXT
);

CREATE TYPE uap_author AS (
    -- ID người dùng bên nguồn
    author_id       TEXT,

    -- [REQUIRED] Tên hiển thị
    display_name    TEXT,

    -- Loại: user, page, bot
    author_type     TEXT,

    -- Số người theo dõi (dùng cho influence calculation)
    followers       INTEGER,

    -- Tài khoản xác minh
    is_verified     BOOLEAN
);

CREATE TYPE uap_attachment AS (
    -- [REQUIRED] Loại: image, video, link
    type            TEXT,

    -- URL của attachment
    url             TEXT,

    -- Mô tả nội dung (OCR text hoặc Caption)
    content         TEXT
);

-- ─── Signals Block ─────────────────────────────────────────────────────────
CREATE TYPE uap_signals AS (
    -- Các chỉ số tương tác
    engagement      uap_engagement,

    -- Thông tin địa lý
    geo             uap_geo
);

CREATE TYPE uap_engagement AS (
    -- Số lượt thích/reaction. Default: 0
    like_count      INTEGER,

    -- Số lượt bình luận. Default: 0
    comment_count   INTEGER,

    -- Số lượt chia sẻ. Default: 0
    share_count     INTEGER,

    -- Số lượt xem. Default: 0
    view_count      INTEGER,

    -- Điểm đánh giá (1-5) nếu là Review
    rating          NUMERIC
);

CREATE TYPE uap_geo AS (
    -- Mã quốc gia (VD: "VN")
    country         TEXT,

    -- Thành phố
    city            TEXT
);

-- ─── Context Block ─────────────────────────────────────────────────────────
CREATE TYPE uap_context AS (
    -- Bài viết match với từ khóa monitoring nào?
    keywords_matched TEXT[],

    -- ID chiến dịch (nếu thuộc chiến dịch đang track)
    campaign_id     TEXT
);

-- ============================================================================
-- VALIDATION RULES
-- ============================================================================
-- 1. uap_version               MUST be "1.0"
-- 2. event_id                  MUST be valid UUID
-- 3. ingest.project_id         MUST NOT be empty
-- 4. ingest.entity.entity_type MUST be valid enum
-- 5. ingest.source.source_type MUST be valid enum
-- 6. content.doc_id            MUST NOT be empty
-- 7. content.text              MUST NOT be empty (or have attachments with content)
-- 8. content.published_at      MUST be valid ISO8601
-- 9. All other fields          OPTIONAL with sensible defaults
-- ============================================================================

-- ============================================================================
-- EXAMPLE UAP MESSAGE
-- ============================================================================
-- {
--   "uap_version": "1.0",
--   "event_id": "b6d6b1e2-9cf3-4e69-8fd0-5b1c8aab9f17",
--   "ingest": {
--     "project_id": "proj_vf8_monitor_01",
--     "entity": {
--       "entity_type": "product",
--       "entity_name": "VF8",
--       "brand": "VinFast"
--     },
--     "source": {
--       "source_id": "src_fb_01",
--       "source_type": "FACEBOOK",
--       "account_ref": {"name": "VinFast Vietnam", "id": "1234567890"}
--     },
--     "batch": {
--       "batch_id": "batch_2026_02_07_001",
--       "mode": "SCHEDULED_CRAWL",
--       "received_at": "2026-02-07T10:00:00Z"
--     },
--     "trace": {
--       "raw_ref": "minio://raw/proj_vf8_monitor_01/facebook/2026-02-07/batch_001.jsonl",
--       "mapping_id": "map_fb_default_v3"
--     }
--   },
--   "content": {
--     "doc_id": "fb_post_987654321",
--     "doc_type": "post",
--     "url": "https://facebook.com/.../posts/987654321",
--     "language": "vi",
--     "published_at": "2026-02-07T09:55:00Z",
--     "author": {
--       "author_id": "fb_user_abc",
--       "display_name": "Nguyễn A",
--       "author_type": "user"
--     },
--     "text": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng."
--   },
--   "signals": {
--     "engagement": {
--       "like_count": 120,
--       "comment_count": 34,
--       "share_count": 5,
--       "view_count": 1111
--     },
--     "geo": {"country": "VN"}
--   },
--   "context": {
--     "keywords_matched": ["vf8", "pin", "giá"],
--     "campaign_id": "id_feb_campaign_2026_01"
--   }
-- }
-- ============================================================================

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================
-- Legacy format (REMOVED): Event Envelope
-- - Broker: RabbitMQ
-- - Queue: analytics.data.collected
-- - Flat structure with payload.meta, payload.content, payload.interaction
--
-- Current format: UAP v1.0
-- - Broker: Kafka
-- - Topic: smap.collector.output
-- - Nested structure with ingest, content, signals blocks
-- - Entity context for AI model selection
-- - Trace block for audit trail
-- - Attachments support for multimodal analysis
-- ============================================================================
