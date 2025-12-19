# Collector ↔ Services Contract Specification

## Tổng quan

Document này định nghĩa contract giữa Collector Service và các services khác:

1. **Crawler → Collector**: Kết quả crawl từ TikTok/YouTube
2. **Analytics → Collector**: Kết quả phân tích từ Analytics Service

**Mục đích:** Đảm bảo các services đồng bộ về format message, behavior, và expectations.

**Version:** 2.0 (Enhanced with limit_info, stats, and Analytics contract)

---

## 1. Message Flow Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 1: CRAWL (Crawler → Collector)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐         ┌─────────────┐         ┌──────────────┐          │
│  │   Crawler    │ ──────► │  RabbitMQ   │ ──────► │  Collector   │          │
│  │   (Worker)   │         │   Queue     │         │   (Results)  │          │
│  └──────────────┘         └─────────────┘         └──────────────┘          │
│                                                                              │
│  Message: EnhancedCrawlerResult                                              │
│  Queue: collector.results                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                   PHASE 2: ANALYZE (Analytics → Collector)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐         ┌─────────────┐         ┌──────────────┐          │
│  │  Analytics   │ ──────► │  RabbitMQ   │ ──────► │  Collector   │          │
│  │   Service    │         │   Queue     │         │   (Results)  │          │
│  └──────────────┘         └─────────────┘         └──────────────┘          │
│                                                                              │
│  Message: AnalyzeResultPayload                                               │
│  Queue: collector.results                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CONTRACT 1: Crawler → Collector (EnhancedCrawlerResult)

### 2.1 Message Structure

```json
{
  "success": true,
  "task_type": "research_and_crawl",
  "limit_info": {
    "requested_limit": 50,
    "applied_limit": 50,
    "total_found": 30,
    "platform_limited": true
  },
  "stats": {
    "successful": 28,
    "failed": 2,
    "skipped": 0,
    "completion_rate": 0.93
  },
  "error": null,
  "payload": [
    {
      "meta": {
        "id": "video123",
        "platform": "tiktok",
        "job_id": "proj123-brand-0",
        "task_type": "research_and_crawl",
        "crawled_at": "2024-01-15T10:35:00Z",
        "published_at": "2024-01-10T08:00:00Z",
        "permalink": "https://tiktok.com/@user/video/123",
        "keyword_source": "brand",
        "lang": "vi",
        "region": "VN",
        "pipeline_version": "1.0.0",
        "fetch_status": "success",
        "fetch_error": null
      },
      "content": { "text": "...", "hashtags": [...] },
      "interaction": { "views": 1000, "likes": 100, ... },
      "author": { "id": "author1", "username": "user1", ... },
      "comments": [...]
    }
  ]
}
```

### 2.2 Field Definitions

#### Root Level Fields

| Field        | Type        | Required | Description                                         |
| ------------ | ----------- | -------- | --------------------------------------------------- |
| `success`    | bool        | ✅       | `true` nếu task hoàn thành (kể cả không có kết quả) |
| `task_type`  | string      | ✅       | `"research_and_crawl"` hoặc `"dryrun_keyword"`      |
| `limit_info` | object      | ✅       | Thông tin về limits và platform limitation          |
| `stats`      | object      | ✅       | Statistics về crawl results                         |
| `error`      | object/null | ❌       | Error details khi `success=false`                   |
| `payload`    | array       | ✅       | Array of crawled content items                      |

#### LimitInfo Object

| Field              | Type | Required | Description                                       |
| ------------------ | ---- | -------- | ------------------------------------------------- |
| `requested_limit`  | int  | ✅       | Limit được request từ Collector                   |
| `applied_limit`    | int  | ✅       | Limit thực tế Crawler áp dụng (sau khi cap)       |
| `total_found`      | int  | ✅       | Số items tìm được trên platform (trước khi crawl) |
| `platform_limited` | bool | ✅       | `true` nếu `total_found < requested_limit`        |

#### Stats Object

| Field             | Type  | Required | Description                                  |
| ----------------- | ----- | -------- | -------------------------------------------- |
| `successful`      | int   | ✅       | Số items crawl thành công                    |
| `failed`          | int   | ✅       | Số items crawl thất bại                      |
| `skipped`         | int   | ✅       | Số items bị skip (duplicate, filtered, etc.) |
| `completion_rate` | float | ✅       | `successful / total_found` (0.0 - 1.0)       |

#### Error Object (khi success=false)

| Field     | Type   | Required | Description                    |
| --------- | ------ | -------- | ------------------------------ |
| `code`    | string | ✅       | Error code (machine-readable)  |
| `message` | string | ✅       | Error message (human-readable) |

#### Payload Item Meta Fields (REQUIRED)

| Field       | Type   | Required | Description                     |
| ----------- | ------ | -------- | ------------------------------- |
| `job_id`    | string | ✅       | Job ID từ Collector để tracking |
| `platform`  | string | ✅       | `"tiktok"` hoặc `"youtube"`     |
| `task_type` | string | ✅       | Task type để routing            |

### 2.3 Response Scenarios

#### Scenario 1: Full Success (tìm đủ limit)

```json
{
  "success": true,
  "task_type": "research_and_crawl",
  "limit_info": {
    "requested_limit": 50,
    "applied_limit": 50,
    "total_found": 50,
    "platform_limited": false
  },
  "stats": {
    "successful": 50,
    "failed": 0,
    "skipped": 0,
    "completion_rate": 1.0
  },
  "payload": [
    /* 50 items */
  ]
}
```

#### Scenario 2: Platform Limited (tìm ít hơn limit)

```json
{
  "success": true,
  "task_type": "research_and_crawl",
  "limit_info": {
    "requested_limit": 50,
    "applied_limit": 50,
    "total_found": 30,
    "platform_limited": true
  },
  "stats": {
    "successful": 28,
    "failed": 2,
    "skipped": 0,
    "completion_rate": 0.93
  },
  "payload": [
    /* 28 items */
  ]
}
```

#### Scenario 3: No Results (keyword không có video)

```json
{
  "success": true,
  "task_type": "research_and_crawl",
  "limit_info": {
    "requested_limit": 50,
    "applied_limit": 50,
    "total_found": 0,
    "platform_limited": true
  },
  "stats": {
    "successful": 0,
    "failed": 0,
    "skipped": 0,
    "completion_rate": 0
  },
  "payload": []
}
```

#### Scenario 4: Task Failed (error xảy ra)

```json
{
  "success": false,
  "task_type": "research_and_crawl",
  "error": {
    "code": "SEARCH_FAILED",
    "message": "TikTok API rate limited"
  },
  "limit_info": {
    "requested_limit": 50,
    "applied_limit": 50,
    "total_found": 0,
    "platform_limited": false
  },
  "stats": {
    "successful": 0,
    "failed": 0,
    "skipped": 0,
    "completion_rate": 0
  },
  "payload": []
}
```

### 2.4 Error Codes

| Code                     | Description           | Retryable  |
| ------------------------ | --------------------- | ---------- |
| `SEARCH_FAILED`          | Search API failed     | ✅ Yes     |
| `RATE_LIMITED`           | Platform rate limit   | ✅ Yes     |
| `RATE_LIMITED_PERMANENT` | Permanent rate limit  | ❌ No      |
| `AUTH_FAILED`            | Authentication failed | ❌ No      |
| `INVALID_KEYWORD`        | Keyword không hợp lệ  | ❌ No      |
| `BLOCKED`                | IP/Account bị block   | ❌ No      |
| `CRAWL_PARTIAL`          | Một số videos fail    | ✅ Partial |
| `TIMEOUT`                | Request timeout       | ✅ Yes     |

### 2.5 Validation Rules

1. **Stats Consistency**: `stats.successful + stats.failed + stats.skipped` PHẢI bằng số items đã attempt crawl
2. **Platform Limited Logic**: `platform_limited = true` khi `total_found < requested_limit`
3. **Completion Rate**: `completion_rate = successful / total_found` (0 nếu total_found = 0)
4. **Payload Length**: `len(payload)` PHẢI bằng `stats.successful`
5. **Required Meta Fields**: Mỗi item trong payload PHẢI có `meta.job_id`, `meta.platform`, `meta.task_type`

---

## 3. CONTRACT 2: Analytics → Collector (AnalyzeResultPayload)

### 3.1 Message Structure

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0-analyze-batch-1",
  "task_type": "analyze_result",
  "batch_size": 10,
  "success_count": 8,
  "error_count": 2
}
```

### 3.2 Field Definitions

| Field           | Type   | Required | Description                                    |
| --------------- | ------ | -------- | ---------------------------------------------- |
| `project_id`    | string | ✅       | Project ID để identify state trong Redis       |
| `job_id`        | string | ✅       | Job ID để tracking và logging                  |
| `task_type`     | string | ✅       | **PHẢI là `"analyze_result"`** để routing đúng |
| `batch_size`    | int    | ✅       | Số items trong batch được gửi để analyze       |
| `success_count` | int    | ✅       | Số items analyze thành công                    |
| `error_count`   | int    | ✅       | Số items analyze thất bại                      |

### 3.3 Response Scenarios

#### Scenario 1: Full Success (tất cả items analyze thành công)

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0-analyze-batch-1",
  "task_type": "analyze_result",
  "batch_size": 10,
  "success_count": 10,
  "error_count": 0
}
```

#### Scenario 2: Partial Success (một số items fail)

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0-analyze-batch-1",
  "task_type": "analyze_result",
  "batch_size": 10,
  "success_count": 7,
  "error_count": 3
}
```

#### Scenario 3: All Failed

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0-analyze-batch-1",
  "task_type": "analyze_result",
  "batch_size": 10,
  "success_count": 0,
  "error_count": 10
}
```

### 3.4 Validation Rules

1. **Task Type**: `task_type` PHẢI bằng `"analyze_result"` - Collector sẽ reject nếu khác
2. **Project ID Required**: `project_id` PHẢI non-empty - Collector extract trực tiếp, không parse từ job_id
3. **Count Consistency**: `success_count + error_count` SHOULD bằng `batch_size`
4. **Non-negative Counts**: `success_count >= 0` và `error_count >= 0`

### 3.5 Collector Processing Logic

```
Khi nhận AnalyzeResultPayload:
1. Validate task_type == "analyze_result"
2. Extract project_id trực tiếp từ payload
3. Increment analyze_done += success_count
4. Increment analyze_errors += error_count
5. Check completion: analyze_done + analyze_errors >= analyze_total
6. Send progress webhook
```

---

## 4. State Tracking Behavior

### 4.1 Two-Phase Processing Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TWO-PHASE PROCESSING                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: CRAWL                          PHASE 2: ANALYZE                    │
│  ┌────────────────────────┐              ┌────────────────────────┐          │
│  │ Crawler → Collector    │              │ Analytics → Collector  │          │
│  │                        │              │                        │          │
│  │ Update:                │              │ Update:                │          │
│  │ - tasks_done += 1      │              │ - analyze_done +=      │          │
│  │ - items_actual +=      │              │     success_count      │          │
│  │     stats.successful   │              │ - analyze_errors +=    │          │
│  │ - items_errors +=      │              │     error_count        │          │
│  │     stats.failed       │              │                        │          │
│  │ - analyze_total +=     │              │                        │          │
│  │     stats.successful   │              │                        │          │
│  └────────────────────────┘              └────────────────────────┘          │
│                                                                              │
│  Completion Check:                                                           │
│  - Crawl: tasks_done + tasks_errors >= tasks_total                           │
│  - Analyze: analyze_done + analyze_errors >= analyze_total                   │
│  - Project DONE: Crawl Complete AND Analyze Complete                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Redis State Structure

```json
{
  "status": "PROCESSING",

  "tasks_total": 6,
  "tasks_done": 4,
  "tasks_errors": 0,

  "items_expected": 300,
  "items_actual": 180,
  "items_errors": 5,

  "analyze_total": 180,
  "analyze_done": 100,
  "analyze_errors": 2,

  "crawl_total": 6,
  "crawl_done": 180,
  "crawl_errors": 5
}
```

### 4.3 Field Descriptions

| Field            | Description                             | Updated By         |
| ---------------- | --------------------------------------- | ------------------ |
| `status`         | Project status: PENDING/PROCESSING/DONE | Collector          |
| `tasks_total`    | Số tasks dispatch (1 task = 1 keyword)  | Dispatcher         |
| `tasks_done`     | Số tasks hoàn thành                     | Crawler response   |
| `tasks_errors`   | Số tasks failed                         | Crawler response   |
| `items_expected` | `tasks_total × limit_per_keyword`       | Dispatcher         |
| `items_actual`   | Tổng `stats.successful` từ Crawler      | Crawler response   |
| `items_errors`   | Tổng `stats.failed` từ Crawler          | Crawler response   |
| `analyze_total`  | = `items_actual` (mỗi item cần analyze) | Crawler response   |
| `analyze_done`   | Tổng `success_count` từ Analytics       | Analytics response |
| `analyze_errors` | Tổng `error_count` từ Analytics         | Analytics response |
| `crawl_total`    | Legacy: = `tasks_total`                 | Dispatcher         |
| `crawl_done`     | Legacy: = `items_actual`                | Crawler response   |
| `crawl_errors`   | Legacy: = `items_errors`                | Crawler response   |

---

## 5. Collector Processing Logic

### 5.1 Crawler Result Processing

```go
// handleProjectResult xử lý EnhancedCrawlerResult từ Crawler
func handleProjectResult(ctx context.Context, res EnhancedCrawlerResult) error {
    // 1. Extract project_id từ payload[0].meta.job_id
    projectID := extractProjectID(res.Payload)

    // 2. Extract limit_info và stats (với fallback)
    limitInfo := res.LimitInfo
    stats := res.Stats
    if limitInfo == nil || stats == nil {
        // Fallback cho backward compatibility
        limitInfo, stats = fallbackLimitInfoAndStats(res)
    }

    // 3. Update task-level counter
    if res.Success {
        stateUC.IncrementTasksDone(ctx, projectID)
    } else {
        stateUC.IncrementTasksErrors(ctx, projectID)
    }

    // 4. Update item-level counters từ stats
    if stats.Successful > 0 {
        stateUC.IncrementItemsActualBy(ctx, projectID, stats.Successful)
        stateUC.IncrementAnalyzeTotalBy(ctx, projectID, stats.Successful)
    }
    if stats.Failed > 0 {
        stateUC.IncrementItemsErrorsBy(ctx, projectID, stats.Failed)
    }

    // 5. Log platform limitation warning
    if limitInfo.PlatformLimited {
        log.Warnf("Platform limited: requested=%d, found=%d",
            limitInfo.RequestedLimit, limitInfo.TotalFound)
    }

    // 6. Send progress webhook và check completion
    sendProgressWebhook(ctx, projectID)
    checkAndUpdateCompletion(ctx, projectID)
}
```

### 5.2 Analytics Result Processing

```go
// handleAnalyzeResult xử lý AnalyzeResultPayload từ Analytics
func handleAnalyzeResult(ctx context.Context, payload AnalyzeResultPayload) error {
    // 1. Validate task_type
    if payload.TaskType != "analyze_result" {
        return ErrInvalidTaskType
    }

    // 2. Validate project_id
    if payload.ProjectID == "" {
        return ErrMissingProjectID
    }

    // 3. Update analyze counters
    if payload.SuccessCount > 0 {
        stateUC.IncrementAnalyzeDoneBy(ctx, payload.ProjectID, payload.SuccessCount)
    }
    if payload.ErrorCount > 0 {
        stateUC.IncrementAnalyzeErrorsBy(ctx, payload.ProjectID, payload.ErrorCount)
    }

    // 4. Send progress webhook và check completion
    sendProgressWebhook(ctx, payload.ProjectID)
    checkAndUpdateCompletion(ctx, payload.ProjectID)
}
```

### 5.3 Fallback Logic (Backward Compatibility)

```go
// fallbackLimitInfoAndStats tạo limit_info và stats từ payload khi Crawler chưa update
func fallbackLimitInfoAndStats(res CrawlerResult) (*LimitInfo, *CrawlStats) {
    payloadLen := len(res.Payload)

    stats := &CrawlStats{
        Successful:     0,
        Failed:         0,
        Skipped:        0,
        CompletionRate: 0,
    }

    if res.Success {
        stats.Successful = payloadLen
        if payloadLen > 0 {
            stats.CompletionRate = 1.0
        }
    } else {
        stats.Failed = payloadLen
    }

    limitInfo := &LimitInfo{
        RequestedLimit:  0,  // Unknown in fallback
        AppliedLimit:    0,
        TotalFound:      payloadLen,
        PlatformLimited: false,
    }

    return limitInfo, stats
}
```

---

## 6. Completion Logic

### 6.1 Completion Check

```go
// IsComplete kiểm tra project đã hoàn thành chưa
func (state *ProjectState) IsComplete() bool {
    return state.IsCrawlComplete() && state.IsAnalyzeComplete()
}

// IsCrawlComplete kiểm tra crawl phase đã hoàn thành
func (state *ProjectState) IsCrawlComplete() bool {
    if state.TasksTotal == 0 {
        // Fallback to legacy fields
        return state.CrawlDone + state.CrawlErrors >= state.CrawlTotal
    }
    return state.TasksDone + state.TasksErrors >= state.TasksTotal
}

// IsAnalyzeComplete kiểm tra analyze phase đã hoàn thành
func (state *ProjectState) IsAnalyzeComplete() bool {
    if state.AnalyzeTotal == 0 {
        return true // No items to analyze
    }
    return state.AnalyzeDone + state.AnalyzeErrors >= state.AnalyzeTotal
}
```

### 6.2 Progress Calculation

```go
// CrawlProgressPercent tính % hoàn thành crawl phase
func (state *ProjectState) CrawlProgressPercent() float64 {
    if state.ItemsExpected == 0 {
        // Fallback to task-level
        if state.TasksTotal == 0 {
            return 0
        }
        return float64(state.TasksDone) / float64(state.TasksTotal) * 100
    }
    return float64(state.ItemsActual) / float64(state.ItemsExpected) * 100
}

// AnalyzeProgressPercent tính % hoàn thành analyze phase
func (state *ProjectState) AnalyzeProgressPercent() float64 {
    if state.AnalyzeTotal == 0 {
        return 100 // No items to analyze = complete
    }
    return float64(state.AnalyzeDone) / float64(state.AnalyzeTotal) * 100
}

// OverallProgressPercent tính % hoàn thành tổng thể
func (state *ProjectState) OverallProgressPercent() float64 {
    crawlProgress := state.CrawlProgressPercent()
    analyzeProgress := state.AnalyzeProgressPercent()
    return (crawlProgress + analyzeProgress) / 2
}
```

---

## 7. Progress Webhook Payload

### 7.1 Webhook Structure

```json
{
  "project_id": "proj123",
  "status": "PROCESSING",
  "overall_progress_percent": 65.5,
  "crawl": {
    "tasks": {
      "total": 6,
      "done": 4,
      "errors": 0,
      "percent": 66.67
    },
    "items": {
      "expected": 300,
      "actual": 180,
      "errors": 5,
      "percent": 60.0
    }
  },
  "analyze": {
    "total": 180,
    "done": 100,
    "errors": 2,
    "percent": 55.56
  },
  "updated_at": "2024-01-15T10:45:00Z"
}
```

### 7.2 Final Completion Webhook

```json
{
  "project_id": "proj123",
  "status": "DONE",
  "overall_progress_percent": 100,
  "crawl": {
    "tasks": { "total": 6, "done": 6, "errors": 0, "percent": 100 },
    "items": { "expected": 300, "actual": 280, "errors": 10, "percent": 93.33 }
  },
  "analyze": {
    "total": 280,
    "done": 275,
    "errors": 5,
    "percent": 98.21
  },
  "completed_at": "2024-01-15T11:00:00Z"
}
```

---

## 8. Example Full Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXAMPLE: 1 Project, 2 keywords, 2 platforms                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT:                                                                      │
│  - project_id: "proj123"                                                     │
│  - brand_keywords: ["iphone", "samsung"]                                     │
│  - limit_per_keyword: 50 (from config)                                       │
│                                                                              │
│  DISPATCH (4 tasks):                                                         │
│  ├── TikTok: { job_id: "proj123-brand-0", keywords: ["iphone"], limit: 50 }  │
│  ├── TikTok: { job_id: "proj123-brand-1", keywords: ["samsung"], limit: 50 } │
│  ├── YouTube: { job_id: "proj123-brand-0", keywords: ["iphone"], limit: 50 } │
│  └── YouTube: { job_id: "proj123-brand-1", keywords: ["samsung"], limit: 50 }│
│                                                                              │
│  STATE AFTER DISPATCH:                                                       │
│  - tasks_total: 4                                                            │
│  - items_expected: 200 (4 × 50)                                              │
│  - analyze_total: 0 (chưa có items)                                          │
│                                                                              │
│  CRAWLER RESPONSES:                                                          │
│  ├── TikTok "iphone": found=50, successful=48, failed=2                      │
│  │   → tasks_done=1, items_actual=48, items_errors=2, analyze_total=48       │
│  ├── TikTok "samsung": found=30, successful=30, failed=0 (platform_limited)  │
│  │   → tasks_done=2, items_actual=78, items_errors=2, analyze_total=78       │
│  ├── YouTube "iphone": found=50, successful=50, failed=0                     │
│  │   → tasks_done=3, items_actual=128, items_errors=2, analyze_total=128     │
│  └── YouTube "samsung": found=50, successful=45, failed=5                    │
│      → tasks_done=4, items_actual=173, items_errors=7, analyze_total=173     │
│                                                                              │
│  STATE AFTER CRAWL COMPLETE:                                                 │
│  - tasks_total: 4, tasks_done: 4, tasks_errors: 0                            │
│  - items_expected: 200, items_actual: 173, items_errors: 7                   │
│  - analyze_total: 173, analyze_done: 0, analyze_errors: 0                    │
│  - Crawl Progress: 86.5% (173/200)                                           │
│                                                                              │
│  ANALYTICS RESPONSES (batches of 50):                                        │
│  ├── Batch 1: success_count=48, error_count=2                                │
│  │   → analyze_done=48, analyze_errors=2                                     │
│  ├── Batch 2: success_count=50, error_count=0                                │
│  │   → analyze_done=98, analyze_errors=2                                     │
│  ├── Batch 3: success_count=50, error_count=0                                │
│  │   → analyze_done=148, analyze_errors=2                                    │
│  └── Batch 4: success_count=23, error_count=0                                │
│      → analyze_done=171, analyze_errors=2                                    │
│                                                                              │
│  FINAL STATE:                                                                │
│  - tasks_total: 4, tasks_done: 4, tasks_errors: 0                            │
│  - items_expected: 200, items_actual: 173, items_errors: 7                   │
│  - analyze_total: 173, analyze_done: 171, analyze_errors: 2                  │
│  - Crawl Progress: 86.5%, Analyze Progress: 100%                             │
│  - Overall Progress: 93.25%                                                  │
│  - Status: DONE (crawl complete AND analyze complete)                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Backward Compatibility

### 9.1 Migration Path

| Phase | Crawler                          | Collector                             |
| ----- | -------------------------------- | ------------------------------------- |
| 1     | Old format (no limit_info/stats) | Fallback logic enabled                |
| 2     | New format with limit_info/stats | Read new format, fallback still works |
| 3     | New format only                  | Remove fallback logic                 |

### 9.2 Collector Fallback Behavior

Khi Crawler chưa update format mới:

- `limit_info = nil` → Collector tạo fallback với `total_found = len(payload)`
- `stats = nil` → Collector tạo fallback với `successful = len(payload)` khi `success=true`
- Platform limitation không detect được trong fallback mode

---

## 10. Summary Checklist

### Crawler Team cần implement:

- [ ] Trả về `limit_info` object với đầy đủ fields
- [ ] Trả về `stats` object với đầy đủ fields
- [ ] Set `platform_limited = true` khi `total_found < requested_limit`
- [ ] Đảm bảo `len(payload) == stats.successful`
- [ ] Include `job_id`, `platform`, `task_type` trong mỗi payload item meta
- [ ] Return `success: true` với `payload: []` khi không có kết quả

### Analytics Team cần implement:

- [ ] Trả về `task_type = "analyze_result"` (REQUIRED)
- [ ] Trả về `project_id` trực tiếp (không để Collector parse từ job_id)
- [ ] Trả về `success_count` và `error_count` chính xác
- [ ] Đảm bảo `success_count + error_count == batch_size`

### Collector sẽ:

- [ ] Parse `limit_info` và `stats` từ Crawler response
- [ ] Fallback khi Crawler chưa update format
- [ ] Validate `task_type = "analyze_result"` từ Analytics
- [ ] Extract `project_id` trực tiếp từ Analytics payload
- [ ] Track state ở cả task-level và item-level
- [ ] Log warning khi `platform_limited = true`
- [ ] Check completion dựa trên cả Crawl và Analyze phases

---

## 11. Related Documents

- `collector-message-processing-detail.md` - Chi tiết xử lý message
- `project-state-behavior.md` - State management behavior
- `event-drivent.md` - Event flow documentation
