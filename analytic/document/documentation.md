# Analytics Engine - Chi Tiết Các Fields và Cơ Chế Tính Toán

## Tổng quan

Document này mô tả chi tiết ý nghĩa, công thức tính toán, và các giá trị có thể có của từng field trong hệ thống analytics. Tất cả dữ liệu được lưu trong bảng `post_analytics` và `crawl_errors` trong PostgreSQL.

---

## 1. Bảng `post_analytics` - Kết Quả Phân Tích Bài Viết

### 1.1. Identifiers và Metadata

| Field        | Kiểu dữ liệu | Ý nghĩa                         | Nguồn tính toán  | Giá trị có thể                               |
| ------------ | ------------ | ------------------------------- | ---------------- | -------------------------------------------- |
| `id`         | `String(50)` | ID duy nhất của bài viết        | Crawler cung cấp | Bất kỳ string ≤ 50 ký tự                     |
| `project_id` | `UUID`       | ID dự án (nullable cho dry-run) | Crawler metadata | UUID hoặc NULL                               |
| `platform`   | `String(20)` | Nền tảng mạng xã hội            | Crawler metadata | "tiktok", "facebook", "youtube", "instagram" |

### 1.2. Timestamps

| Field          | Kiểu dữ liệu | Ý nghĩa                    | Nguồn tính toán              | Giá trị có thể      |
| -------------- | ------------ | -------------------------- | ---------------------------- | ------------------- |
| `published_at` | `TIMESTAMP`  | Thời gian đăng bài gốc     | Crawler metadata             | Timestamp hợp lệ    |
| `analyzed_at`  | `TIMESTAMP`  | Thời gian xử lý analytics  | `datetime.now(timezone.utc)` | Timestamp tự động   |
| `crawled_at`   | `TIMESTAMP`  | Thời gian crawler thu thập | Crawler metadata             | Timestamp hoặc NULL |

### 1.3. Sentiment Analysis (Phân Tích Cảm Xúc)

#### Overall Sentiment (Cảm xúc tổng thể)

| Field                     | Kiểu dữ liệu | Ý nghĩa                     | Công thức tính toán            | Giá trị có thể                                                                                      |
| ------------------------- | ------------ | --------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------- |
| `overall_sentiment`       | `String(10)` | Nhãn cảm xúc tổng thể       | PhoBERT model + thresholds     | "POSITIVE", "NEGATIVE", "NEUTRAL"                                                                   |
| `overall_sentiment_score` | `Float`      | Điểm cảm xúc số (-1 đến +1) | 5-class rating → score mapping | -1.0 ≤ score ≤ 1.0                                                                                  |
| `overall_confidence`      | `Float`      | Độ tin cậy của prediction   | `max(probabilities)`           | 0.0 ≤ confidence ≤ 1.0                                                                              |
| `sentiment_probabilities` | `JSONB`      | Phân phối xác suất đầy đủ   | PhoBERT softmax output         | `{"VERY_NEGATIVE": 0.01, "NEGATIVE": 0.05, "NEUTRAL": 0.1, "POSITIVE": 0.2, "VERY_POSITIVE": 0.64}` |

**Chi tiết tính toán Overall Sentiment:**

1. **PhoBERT 3-class mapping:**

   - Index 0 (NEG) → Rating 1 → Score -1.0
   - Index 1 (POS) → Rating 5 → Score +1.0
   - Index 2 (NEU) → Rating 3 → Score 0.0

2. **Label assignment:**
   ```python
   if score > 0.25: return "POSITIVE"
   elif score < -0.25: return "NEGATIVE"
   else: return "NEUTRAL"
   ```

#### Aspect-Based Sentiment (Cảm xúc theo khía cạnh)

| Field               | Kiểu dữ liệu | Ý nghĩa                          | Công thức tính toán                  | Giá trị có thể        |
| ------------------- | ------------ | -------------------------------- | ------------------------------------ | --------------------- |
| `aspects_breakdown` | `JSONB`      | Phân tích cảm xúc theo khía cạnh | Context windowing + weighted average | Xem chi tiết bên dưới |

**Cấu trúc `aspects_breakdown`:**

```json
{
  "DESIGN": {
    "sentiment": "POSITIVE",
    "score": 0.8,
    "confidence": 0.92,
    "mentions": 3
  },
  "PERFORMANCE": {
    "sentiment": "NEGATIVE",
    "score": -0.6,
    "confidence": 0.87,
    "mentions": 2
  },
  "PRICE": { ... },
  "SERVICE": { ... },
  "GENERAL": { ... }
}
```

**Khía cạnh (Aspects) có thể:**

- **DESIGN**: Ngoại hình, thiết kế, màu sắc
- **PERFORMANCE**: Pin, sạc, tốc độ, kỹ thuật
- **PRICE**: Giá cả, giá trị, khả năng chi trả
- **SERVICE**: Dịch vụ khách hàng, bảo hành, hỗ trợ
- **GENERAL**: Các khía cạnh chung khác

**Thuật toán Context Windowing:**

1. Tạo context window ±30 ký tự quanh keyword
2. Cắt tại dấu câu [".", ",", "!", "?"] hoặc từ chuyển tiếp ["nhưng", "tuy nhiên"]
3. Snap to word boundaries để tránh cắt từ
4. Fallback về full text nếu context quá ngắn

**Weighted Aggregation cho nhiều mentions:**

```python
avg_score = Σ(score_i × confidence_i) / Σ(confidence_i)
avg_confidence = total_confidence / num_mentions
```

### 1.4. Intent Classification (Phân Loại Ý Định)

| Field               | Kiểu dữ liệu | Ý nghĩa                     | Công thức tính toán                          | Giá trị có thể           |
| ------------------- | ------------ | --------------------------- | -------------------------------------------- | ------------------------ |
| `primary_intent`    | `String(20)` | Ý định chính của bài viết   | Regex pattern matching + priority resolution | Xem bảng Intent bên dưới |
| `intent_confidence` | `Float`      | Độ tin cậy phân loại ý định | `min(0.5 + (num_matches * 0.1), 1.0)`        | 0.5 ≤ confidence ≤ 1.0   |

**Intent Categories và Priorities:**

| Intent         | Priority | Ý nghĩa                 | Pattern examples              | Action          |
| -------------- | -------- | ----------------------- | ----------------------------- | --------------- |
| **CRISIS**     | 10       | Khủng hoảng thương hiệu | "tẩy chay", "lừa đảo", "scam" | Alert + Process |
| **SEEDING**    | 9        | Spam marketing ẩn       | Phone numbers, native ads     | **SKIP AI**     |
| **SPAM**       | 8        | Rác quảng cáo rõ ràng   | "vay tiền", "bán sim"         | **SKIP AI**     |
| **COMPLAINT**  | 7        | Khiếu nại khách hàng    | "kém chất lượng", "thất vọng" | Flag + Process  |
| **LEAD**       | 5        | Cơ hội bán hàng         | "muốn mua", "ở đâu bán"       | Flag + Process  |
| **SUPPORT**    | 4        | Hỗ trợ kỹ thuật         | "làm sao để", "hướng dẫn"     | Flag + Process  |
| **DISCUSSION** | 1        | Thảo luận bình thường   | Default                       | Process         |

**Priority Resolution:**

```python
best_intent = max(matched_intents, key=lambda i: i.priority)
confidence = min(0.5 + (num_pattern_matches * 0.1), 1.0)
```

### 1.5. Impact Calculation (Tính Điểm Tác Động)

#### Core Impact Fields

| Field          | Kiểu dữ liệu | Ý nghĩa                 | Công thức tính toán                   | Giá trị có thể                      |
| -------------- | ------------ | ----------------------- | ------------------------------------- | ----------------------------------- |
| `impact_score` | `Float`      | Điểm tác động chuẩn hóa | Xem công thức chi tiết bên dưới       | 0.0 ≤ score ≤ 100.0                 |
| `risk_level`   | `String(10)` | Mức độ rủi ro           | Impact score + sentiment + KOL status | "CRITICAL", "HIGH", "MEDIUM", "LOW" |
| `is_viral`     | `Boolean`    | Có viral không          | `impact_score >= 70.0`                | true/false                          |
| `is_kol`       | `Boolean`    | Có phải KOL không       | `follower_count >= 50000`             | true/false                          |

**Công thức Impact Score:**

```python
# 1. Engagement Score
engagement_score = (
    views * 0.01 +
    likes * 1.0 +
    comments * 2.0 +
    saves * 3.0 +
    shares * 5.0
)

# 2. Reach Score
reach_score = log10(followers + 1)
if is_verified:
    reach_score *= 1.2

# 3. Platform Multiplier
platform_multipliers = {
    "tiktok": 1.0,
    "facebook": 1.2,
    "youtube": 1.5,
    "instagram": 1.1
}

# 4. Sentiment Amplifier
sentiment_amplifiers = {
    "NEGATIVE": 1.5,
    "NEUTRAL": 1.0,
    "POSITIVE": 1.1
}

# 5. Raw Impact
raw_impact = (
    engagement_score *
    reach_score *
    platform_multipliers[platform] *
    sentiment_amplifiers[sentiment]
)

# 6. Normalized Impact Score (0-100)
impact_score = min(100.0, (raw_impact / MAX_RAW_SCORE_CEILING) * 100.0)
```

**Risk Level Matrix:**

| Conditions                                                             | Risk Level   | Ý nghĩa                                |
| ---------------------------------------------------------------------- | ------------ | -------------------------------------- |
| `impact_score >= 70 AND sentiment == "NEGATIVE" AND is_kol == true`    | **CRITICAL** | Cao tác động + tiêu cực + KOL          |
| `impact_score >= 70 AND sentiment == "NEGATIVE" AND is_kol == false`   | **HIGH**     | Cao tác động + tiêu cực + người thường |
| `impact_score >= 40 AND impact_score < 70 AND sentiment == "NEGATIVE"` | **MEDIUM**   | Trung bình tác động + tiêu cực         |
| `impact_score >= 60 AND sentiment IN ["NEUTRAL", "POSITIVE"]`          | **MEDIUM**   | Cao tác động + tích cực/trung tính     |
| All other cases                                                        | **LOW**      | Các trường hợp còn lại                 |

#### Impact Breakdown Details

| Field              | Kiểu dữ liệu | Ý nghĩa                   | Giá trị có thể        |
| ------------------ | ------------ | ------------------------- | --------------------- |
| `impact_breakdown` | `JSONB`      | Chi tiết tính toán impact | Xem cấu trúc bên dưới |

**Cấu trúc `impact_breakdown`:**

```json
{
  "engagement_score": 850.5,
  "reach_score": 5.2,
  "platform_multiplier": 1.0,
  "sentiment_amplifier": 1.5,
  "raw_impact": 6606.9,
  "is_viral": true,
  "is_kol": false,
  "viral_threshold": 70.0,
  "kol_threshold": 50000
}
```

### 1.6. Keyword Extraction (Trích Xuất Từ Khóa)

| Field      | Kiểu dữ liệu | Ý nghĩa                        | Công thức tính toán                 | Giá trị có thể        |
| ---------- | ------------ | ------------------------------ | ----------------------------------- | --------------------- |
| `keywords` | `JSONB`      | Danh sách từ khóa và khía cạnh | Hybrid extraction (Dictionary + AI) | Xem cấu trúc bên dưới |

**Cấu trúc `keywords`:**

```json
{
  "extracted": [
    {
      "keyword": "thiết kế",
      "aspect": "DESIGN",
      "score": 1.0,
      "source": "DICT",
      "rank": 1
    },
    {
      "keyword": "pin",
      "aspect": "PERFORMANCE",
      "score": 0.85,
      "source": "AI",
      "rank": 2
    }
  ],
  "metadata": {
    "extraction_time": 0.123,
    "total_candidates": 45,
    "dict_matches": 3,
    "ai_matches": 12
  }
}
```

**Hybrid Extraction Process:**

1. **Dictionary Matching** (O(1) lookup):

   - Score: `1.0` (perfect match)
   - Source: `"DICT"`
   - Ưu tiên cao nhất

2. **AI Discovery** (nếu dict_matches < 5):

   - Sử dụng SpaCy + YAKE
   - Score: `1.0 - yake_score`
   - Source: `"AI"`

3. **Aspect Mapping:**
   - Exact match trong dictionary → aspect tương ứng
   - Substring match → aspect tương ứng
   - Không match → `"GENERAL"`

### 1.7. Raw Engagement Metrics (Số Liệu Tương Tác Gốc)

| Field            | Kiểu dữ liệu | Ý nghĩa                  | Nguồn        | Giá trị có thể         |
| ---------------- | ------------ | ------------------------ | ------------ | ---------------------- |
| `view_count`     | `Integer`    | Số lượt xem              | Crawler data | 0 ≤ views ≤ 2^31-1     |
| `like_count`     | `Integer`    | Số lượt thích            | Crawler data | 0 ≤ likes ≤ 2^31-1     |
| `comment_count`  | `Integer`    | Số bình luận             | Crawler data | 0 ≤ comments ≤ 2^31-1  |
| `share_count`    | `Integer`    | Số lượt chia sẻ          | Crawler data | 0 ≤ shares ≤ 2^31-1    |
| `save_count`     | `Integer`    | Số lượt lưu              | Crawler data | 0 ≤ saves ≤ 2^31-1     |
| `follower_count` | `Integer`    | Số người theo dõi author | Crawler data | 0 ≤ followers ≤ 2^31-1 |

### 1.8. Processing Metadata (Metadata Xử Lý)

| Field                | Kiểu dữ liệu | Ý nghĩa                        | Nguồn tính toán          | Giá trị có thể    |
| -------------------- | ------------ | ------------------------------ | ------------------------ | ----------------- |
| `processing_time_ms` | `Integer`    | Thời gian xử lý (milliseconds) | Timer trong orchestrator | 0 ≤ time ≤ 2^31-1 |
| `model_version`      | `String(50)` | Version của PhoBERT model      | Model metadata           | String ≤ 50 chars |
| `pipeline_version`   | `String(50)` | Version của analytics pipeline | Application version      | String ≤ 50 chars |

### 1.9. Batch và Job Context

| Field            | Kiểu dữ liệu  | Ý nghĩa                | Nguồn         | Giá trị có thể               |
| ---------------- | ------------- | ---------------------- | ------------- | ---------------------------- |
| `job_id`         | `String(100)` | ID của crawler job     | Crawler event | String ≤ 100 chars hoặc NULL |
| `batch_index`    | `Integer`     | Thứ tự batch trong job | Crawler event | 0 ≤ index ≤ 2^31-1 hoặc NULL |
| `task_type`      | `String(30)`  | Loại task crawler      | Crawler event | "research_and_crawl", etc.   |
| `keyword_source` | `String(200)` | Keyword gốc để crawl   | Crawler event | String ≤ 200 chars           |

### 1.10. Error Tracking (Theo Dõi Lỗi)

| Field           | Kiểu dữ liệu | Ý nghĩa             | Nguồn          | Giá trị có thể                          |
| --------------- | ------------ | ------------------- | -------------- | --------------------------------------- |
| `fetch_status`  | `String(10)` | Trạng thái crawl    | Crawler result | "success", "error", "partial"           |
| `fetch_error`   | `Text`       | Thông báo lỗi ngắn  | Crawler error  | Text hoặc NULL                          |
| `error_code`    | `String(50)` | Mã lỗi chuẩn        | Crawler error  | "RATE_LIMITED", "CONTENT_REMOVED", etc. |
| `error_details` | `JSONB`      | Chi tiết lỗi đầy đủ | Crawler error  | JSON object hoặc NULL                   |

---

## 2. Bảng `crawl_errors` - Lỗi Crawler Chi Tiết

### 2.1. Identifiers

| Field        | Kiểu dữ liệu  | Ý nghĩa               | Constraints    | Giá trị có thể             |
| ------------ | ------------- | --------------------- | -------------- | -------------------------- |
| `id`         | `Integer`     | Primary key tự tăng   | AUTO_INCREMENT | 1, 2, 3, ...               |
| `content_id` | `String(50)`  | ID của content bị lỗi | NOT NULL       | String ≤ 50 chars          |
| `project_id` | `UUID`        | ID dự án              | NULLABLE       | UUID hoặc NULL             |
| `job_id`     | `String(100)` | ID của crawler job    | NOT NULL       | String ≤ 100 chars         |
| `platform`   | `String(20)`  | Nền tảng              | NOT NULL       | "tiktok", "facebook", etc. |

### 2.2. Error Classification

| Field            | Kiểu dữ liệu | Ý nghĩa                | Constraints | Giá trị có thể            |
| ---------------- | ------------ | ---------------------- | ----------- | ------------------------- |
| `error_code`     | `String(50)` | Mã lỗi chuẩn           | NOT NULL    | Xem bảng Error Codes      |
| `error_category` | `String(30)` | Nhóm lỗi               | NOT NULL    | Xem bảng Error Categories |
| `error_message`  | `Text`       | Thông báo lỗi chi tiết | NULLABLE    | Text message              |
| `error_details`  | `JSONB`      | Metadata lỗi           | NULLABLE    | JSON object               |

**Error Categories:**

| Category          | Ý nghĩa           | Error Codes                                               |
| ----------------- | ----------------- | --------------------------------------------------------- |
| **Rate Limiting** | Giới hạn tần suất | `RATE_LIMITED`, `AUTH_FAILED`, `ACCESS_DENIED`            |
| **Content**       | Vấn đề nội dung   | `CONTENT_REMOVED`, `CONTENT_NOT_FOUND`, `PRIVATE_ACCOUNT` |
| **Network**       | Lỗi mạng          | `NETWORK_ERROR`, `TIMEOUT`, `DNS_ERROR`                   |
| **Parsing**       | Lỗi phân tích     | `PARSE_ERROR`, `INVALID_URL`, `STRUCTURE_CHANGED`         |

### 2.3. References và Timestamps

| Field        | Kiểu dữ liệu | Ý nghĩa             | Constraints   | Giá trị có thể |
| ------------ | ------------ | ------------------- | ------------- | -------------- |
| `permalink`  | `Text`       | URL gốc của content | NULLABLE      | Valid URL      |
| `created_at` | `TIMESTAMP`  | Thời gian ghi lỗi   | DEFAULT NOW() | Timestamp      |

---

## 3. Text Preprocessing Fields

### 3.1. Content Merging Priority

**Thứ tự ưu tiên merge content:**

1. **Transcription** (cao nhất) - Transcript video/audio
2. **Caption** (trung bình) - Mô tả bài viết
3. **Top Comments** (thấp nhất) - Comments có nhiều like

**Formula:**

```python
merged_text = ". ".join([
    transcription if transcription else "",
    caption if caption else "",
    ". ".join(sorted_top_comments)
]).strip(". ")
```

### 3.2. Normalization Steps

**Vietnamese Teencode/Slang Mapping (58 entries):**

- "ko" → "không"
- "dc" → "được"
- "vkl" → "rất"
- "vcl" → "quá"
- "tks" → "cảm ơn"
- "tqt" → "quá trình"
- etc.

**Regex Patterns:**

- **URLs**: `r"(?:http[s]?://|www\.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"`
- **Vietnamese Phone**: `r"(03|05|07|08|09|01[2689])\d{8}"`
- **Hashtags**: `r"#(\w+)"` → `r"\1"`

### 3.3. Quality Statistics

| Statistic           | Công thức                       | Ý nghĩa               | Ngưỡng     |
| ------------------- | ------------------------------- | --------------------- | ---------- |
| `total_length`      | `len(clean_text)`               | Độ dài text sau clean | -          |
| `is_too_short`      | `length < min_text_length`      | Text quá ngắn         | 10 chars   |
| `hashtag_ratio`     | `hashtag_count / word_count`    | Tỷ lệ hashtag         | 0.0-1.0    |
| `reduction_ratio`   | `(original - clean) / original` | Tỷ lệ thu gọn         | 0.0-1.0    |
| `has_transcription` | `bool(transcription)`           | Có transcript không   | true/false |
| `has_phone`         | `bool(phone_pattern.search())`  | Có số điện thoại      | true/false |
| `has_spam_keyword`  | `bool(spam_patterns.search())`  | Có từ khóa spam       | true/false |

**Spam Keywords:**

- "vay vốn", "lãi suất", "giải ngân"
- "bán sim", "tuyển dụng"
- "nhận tiền", "kiếm tiền"

---

## 4. Configuration và Constants

### 4.1. Environment Variables

| Variable                      | Default | Ý nghĩa                           | Ảnh hưởng đến fields |
| ----------------------------- | ------- | --------------------------------- | -------------------- |
| `CONTEXT_WINDOW_SIZE`         | 30      | Kích thước context window (chars) | `aspects_breakdown`  |
| `THRESHOLD_POSITIVE`          | 0.25    | Ngưỡng sentiment POSITIVE         | `overall_sentiment`  |
| `THRESHOLD_NEGATIVE`          | -0.25   | Ngưỡng sentiment NEGATIVE         | `overall_sentiment`  |
| `MAX_KEYWORDS`                | 30      | Số lượng keywords tối đa          | `keywords.extracted` |
| `INTENT_CONFIDENCE_THRESHOLD` | 0.5     | Ngưỡng tin cậy intent tối thiểu   | `intent_confidence`  |

### 4.2. Model Constants

| Constant                | Value                                        | Ý nghĩa                      |
| ----------------------- | -------------------------------------------- | ---------------------------- |
| `SENTIMENT_MAP`         | `{0: 1, 1: 5, 2: 3}`                         | PhoBERT class → rating       |
| `SCORE_MAP`             | `{1: -1.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 1.0}` | Rating → sentiment score     |
| `MAX_RAW_SCORE_CEILING` | Calculated dynamically                       | Chuẩn hóa impact score       |
| `KOL_THRESHOLD`         | 50000                                        | Ngưỡng followers để là KOL   |
| `VIRAL_THRESHOLD`       | 70.0                                         | Ngưỡng impact score để viral |

---

## 5. Data Flow và Dependencies

### 5.1. Processing Pipeline Order

```
1. Text Preprocessing → clean_text, stats
2. Intent Classification → intent, should_skip
3. Skip Check → Nếu should_skip = true, bỏ qua các bước AI
4. Keyword Extraction → keywords với aspects
5. Sentiment Analysis → overall + aspect sentiments
6. Impact Calculation → impact_score, risk_level, flags
7. Database Persistence → Lưu vào post_analytics
```

### 5.2. Skip Logic

**Điều kiện skip AI processing:**

```python
should_skip = (
    preprocessing.is_too_short OR
    preprocessing.has_spam_keyword OR
    intent.should_skip  # SPAM hoặc SEEDING
)
```

### 5.3. Field Dependencies

- `overall_sentiment` ← PhoBERT model output
- `aspects_breakdown` ← `overall_sentiment` + `keywords` + context windowing
- `impact_score` ← engagement metrics + reach + platform + sentiment
- `risk_level` ← `impact_score` + `overall_sentiment` + `is_kol`
- `is_viral` ← `impact_score >= 70.0`
- `is_kol` ← `follower_count >= 50000`

---

## 6. Validation và Constraints

### 6.1. Business Rules

- `project_id` có thể NULL (cho dry-run tasks)
- `overall_sentiment_score` phải trong range [-1.0, 1.0]
- `impact_score` phải trong range [0.0, 100.0]
- `intent_confidence` phải trong range [0.5, 1.0]
- Tất cả engagement counts phải ≥ 0

### 6.2. Data Quality Checks

- `keywords.extracted` không được rỗng (trừ khi skip)
- `aspects_breakdown` phải chứa ít nhất 1 aspect
- `sentiment_probabilities` phải sum = 1.0
- `processing_time_ms` phải > 0
- `published_at` không được trong tương lai

---

## 7. Performance Considerations

### 7.1. Database Indexes

**Indexes trên `post_analytics`:**

- `idx_post_analytics_job_id` (job_id)
- `idx_post_analytics_fetch_status` (fetch_status)
- `idx_post_analytics_task_type` (task_type)
- `idx_post_analytics_error_code` (error_code)

**Indexes trên `crawl_errors`:**

- `idx_crawl_errors_project_id` (project_id)
- `idx_crawl_errors_error_code` (error_code)
- `idx_crawl_errors_created_at` (created_at)
- `idx_crawl_errors_job_id` (job_id)

### 7.2. Processing Times

| Module                | Average Time   | Complexity          |
| --------------------- | -------------- | ------------------- |
| Text Preprocessing    | ~1-2ms         | O(n)                |
| Intent Classification | ~0.015ms       | O(p) patterns       |
| Keyword Extraction    | ~100-300ms     | O(k) + AI           |
| Sentiment Analysis    | ~80-120ms      | O(1) per prediction |
| Impact Calculation    | ~0.1ms         | O(1)                |
| **Total Pipeline**    | **~200-500ms** | -                   |

---

## 8. Error Handling và Logging

### 8.1. Graceful Degradation

- Nếu PhoBERT fail → skip sentiment analysis, lưu error
- Nếu keyword extraction fail → fallback to empty keywords
- Nếu aspect analysis fail → fallback to overall sentiment
- Nếu impact calculation fail → default impact_score = 0.0

### 8.2. Error Storage

**post_analytics errors:**

- `fetch_status` = "error"
- `fetch_error` = short message
- `error_code` = standardized code
- `error_details` = full JSON details

**crawl_errors table:**

- Separate storage cho crawler-specific errors
- Detailed categorization và analysis
- Không ảnh hưởng đến analytics results

---

_Document này được tạo tự động từ source code analysis và được cập nhật định kỳ theo phiên bản hệ thống._
