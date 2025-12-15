# Integration Guide: Analytics Service

**Ngày tạo:** 2025-12-15  
**Cập nhật:** 2025-12-15 - Batch processing via MinIO  
**Liên quan:** [project-state-proposal.md](./project-state-proposal.md)

---

## 1. Tổng quan

### 1.1. Flow tổng thể

```
Crawler ──(upload)──► MinIO
    │
    └──(data.collected event)──► Analytics
                                     │
                                     ├── Fetch data từ MinIO (batch)
                                     │
                                     ├── Analyze batch
                                     │
                                     └──(analyze.result)──► Collector ──webhook──► Project
```

### 1.2. Lý do thiết kế

- **MinIO**: Tránh nghẽn RabbitMQ khi có nhiều data
- **Batch processing**: Analytics xử lý nhiều items cùng lúc
- **Collector là single point**: Gọi webhook, không duplicate logic

---

## 2. Input: Event `data.collected`

### 2.1. Exchange & Queue

| Component   | Value                               |
| ----------- | ----------------------------------- |
| Exchange    | `smap.events`                       |
| Routing Key | `data.collected`                    |
| Queue       | `analytics.data.collected` (tự đặt) |

### 2.2. Event Format (từ Crawler)

```json
{
  "event_id": "evt_def456",
  "timestamp": "2025-12-15T11:00:00Z",
  "payload": {
    "project_id": "proj_xyz",
    "user_id": "user_123",
    "job_id": "proj_xyz-brand-0",
    "minio_path": "/data/proj_xyz/batch_001.json",
    "item_count": 50,
    "platform": "tiktok"
  }
}
```

### 2.3. Event Struct

```go
// analytics/internal/events/types.go

type DataCollectedEvent struct {
    EventID   string                 `json:"event_id"`
    Timestamp time.Time              `json:"timestamp"`
    Payload   DataCollectedPayload   `json:"payload"`
}

type DataCollectedPayload struct {
    ProjectID  string `json:"project_id"`
    UserID     string `json:"user_id"`
    JobID      string `json:"job_id"`
    MinioPath  string `json:"minio_path"`
    ItemCount  int    `json:"item_count"`
    Platform   string `json:"platform"`
}
```

---

## 3. MinIO Data Format

### 3.1. File Structure

Analytics fetch file từ `minio_path`, file chứa array of `CrawlerContent`:

```json
[
  {
    "meta": {
      "id": "video_123",
      "platform": "tiktok",
      "job_id": "proj_xyz-brand-0",
      "task_type": "research_and_crawl",
      "crawled_at": "2025-12-15T10:30:00Z",
      "published_at": "2025-12-10T08:00:00Z",
      "permalink": "https://tiktok.com/@user/video/123",
      "keyword_source": "VinFast"
    },
    "content": {
      "text": "Review VinFast VF8...",
      "duration": 60,
      "hashtags": ["vinfast", "vf8", "review"]
    },
    "interaction": {
      "views": 10000,
      "likes": 500,
      "comments_count": 50
    },
    "author": {
      "id": "author_456",
      "name": "Tech Reviewer",
      "followers": 50000
    },
    "comments": [...]
  },
  // ... more items
]
```

### 3.2. Content Struct (same as Collector)

```go
// analytics/internal/models/content.go

type CrawlerContent struct {
    Meta        CrawlerContentMeta        `json:"meta"`
    Content     CrawlerContentData        `json:"content"`
    Interaction CrawlerContentInteraction `json:"interaction"`
    Author      CrawlerContentAuthor      `json:"author"`
    Comments    []CrawlerComment          `json:"comments,omitempty"`
}

type CrawlerContentMeta struct {
    ID            string `json:"id"`
    Platform      string `json:"platform"`
    JobID         string `json:"job_id"`
    TaskType      string `json:"task_type"`
    CrawledAt     string `json:"crawled_at"`
    PublishedAt   string `json:"published_at"`
    Permalink     string `json:"permalink"`
    KeywordSource string `json:"keyword_source"`
    // ... other fields
}
```

---

## 4. Output: Message `analyze.result`

### 4.1. Exchange & Queue

| Component   | Value                                      |
| ----------- | ------------------------------------------ |
| Exchange    | `results.inbound`                          |
| Routing Key | `analyze.result`                           |
| Queue       | `results.inbound.data` (Collector consume) |

### 4.2. Message Format

**QUAN TRỌNG:** Analytics gửi **1 message per batch**, không phải per item.

```json
{
  "success": true,
  "payload": {
    "project_id": "proj_xyz",
    "job_id": "proj_xyz-brand-0",
    "task_type": "analyze_result",
    "batch_size": 50,
    "success_count": 48,
    "error_count": 2,
    "results": [
      {
        "content_id": "video_123",
        "sentiment": "positive",
        "sentiment_score": 0.85,
        "topics": ["technology", "electric_vehicle"],
        "entities": [
          { "name": "VinFast", "type": "brand" },
          { "name": "VF8", "type": "product" }
        ]
      }
      // ... more results
    ],
    "errors": [
      {
        "content_id": "video_456",
        "error": "Failed to extract text"
      }
    ]
  }
}
```

### 4.3. Result Struct

```go
// analytics/internal/publisher/types.go

type AnalyzeResultMessage struct {
    Success bool                 `json:"success"`
    Payload AnalyzeResultPayload `json:"payload"`
}

type AnalyzeResultPayload struct {
    ProjectID    string          `json:"project_id"`
    JobID        string          `json:"job_id"`
    TaskType     string          `json:"task_type"`  // "analyze_result"
    BatchSize    int             `json:"batch_size"`
    SuccessCount int             `json:"success_count"`
    ErrorCount   int             `json:"error_count"`
    Results      []AnalyzeItem   `json:"results,omitempty"`
    Errors       []AnalyzeError  `json:"errors,omitempty"`
}

type AnalyzeItem struct {
    ContentID      string         `json:"content_id"`
    Sentiment      string         `json:"sentiment,omitempty"`
    SentimentScore float64        `json:"sentiment_score,omitempty"`
    Topics         []string       `json:"topics,omitempty"`
    Entities       []Entity       `json:"entities,omitempty"`
    // ... other analysis fields
}

type AnalyzeError struct {
    ContentID string `json:"content_id"`
    Error     string `json:"error"`
}

type Entity struct {
    Name string `json:"name"`
    Type string `json:"type"`
}
```

---

## 5. Processing Flow

### 5.1. Consumer

```go
// analytics/internal/consumer/consumer.go

func (c *consumer) HandleDataCollected(ctx context.Context, event DataCollectedEvent) error {
    log.Infof("Received data.collected: project_id=%s, minio_path=%s, item_count=%d",
        event.Payload.ProjectID, event.Payload.MinioPath, event.Payload.ItemCount)

    // 1. Fetch data from MinIO
    contents, err := c.minioClient.FetchBatch(ctx, event.Payload.MinioPath)
    if err != nil {
        return fmt.Errorf("failed to fetch from MinIO: %w", err)
    }

    // 2. Analyze batch
    results, errors := c.analyzer.AnalyzeBatch(ctx, contents)

    // 3. Build result message
    resultMsg := AnalyzeResultMessage{
        Success: len(errors) < len(contents), // Success if majority succeeded
        Payload: AnalyzeResultPayload{
            ProjectID:    event.Payload.ProjectID,
            JobID:        event.Payload.JobID,
            TaskType:     "analyze_result",
            BatchSize:    len(contents),
            SuccessCount: len(results),
            ErrorCount:   len(errors),
            Results:      results,
            Errors:       errors,
        },
    }

    // 4. Publish to Collector
    return c.publisher.PublishAnalyzeResult(ctx, resultMsg)
}
```

### 5.2. Publisher

```go
// analytics/internal/publisher/rabbitmq.go

const (
    ExchangeName = "results.inbound"
    RoutingKey   = "analyze.result"
)

func (p *publisher) PublishAnalyzeResult(ctx context.Context, msg AnalyzeResultMessage) error {
    body, err := json.Marshal(msg)
    if err != nil {
        return err
    }

    return p.channel.PublishWithContext(ctx,
        ExchangeName,
        RoutingKey,
        false, false,
        amqp.Publishing{
            ContentType: "application/json",
            Body:        body,
        },
    )
}
```

---

## 6. Collector Side: Handle Batch Result

### 6.1. Handler Update

Collector cần handle batch result (không phải per-item):

```go
// collector/internal/results/usecase/result.go

func (uc implUseCase) handleAnalyzeResult(ctx context.Context, res models.CrawlerResult) error {
    // Extract payload
    payload, err := uc.extractAnalyzePayload(ctx, res.Payload)
    if err != nil {
        return err
    }

    projectID := payload.ProjectID

    // Update counters based on batch results
    // Increment by success_count and error_count (not by 1)
    if payload.SuccessCount > 0 {
        uc.stateUC.IncrementAnalyzeDoneBy(ctx, projectID, int64(payload.SuccessCount))
    }
    if payload.ErrorCount > 0 {
        uc.stateUC.IncrementAnalyzeErrorsBy(ctx, projectID, int64(payload.ErrorCount))
    }

    // Get state and notify progress
    state, _ := uc.stateUC.GetState(ctx, projectID)
    userID, _ := uc.stateUC.GetUserID(ctx, projectID)

    progressReq := uc.buildProgressRequest(projectID, userID, state)
    uc.webhookUC.NotifyProgress(ctx, progressReq)

    // Check completion
    completed, _ := uc.stateUC.CheckCompletion(ctx, projectID)
    if completed {
        uc.webhookUC.NotifyCompletion(ctx, progressReq)
    }

    return nil
}

type AnalyzePayload struct {
    ProjectID    string `json:"project_id"`
    JobID        string `json:"job_id"`
    TaskType     string `json:"task_type"`
    BatchSize    int    `json:"batch_size"`
    SuccessCount int    `json:"success_count"`
    ErrorCount   int    `json:"error_count"`
}
```

### 6.2. State Interface Update

```go
// collector/internal/state/interface.go

type UseCase interface {
    // ... existing methods

    // Analyze operations - increment by N (for batch)
    IncrementAnalyzeDoneBy(ctx, projectID string, count int64) error
    IncrementAnalyzeErrorsBy(ctx, projectID string, count int64) error
}
```

---

## 7. Analyze Total: Khi nào set?

### Decision: Collector set khi nhận crawl result

Vì Crawler gửi batch, Collector biết `item_count` từ crawl result:

```go
// collector/internal/results/usecase/result.go

func (uc implUseCase) handleProjectResult(ctx context.Context, res models.CrawlerResult) error {
    // ... existing logic

    if res.Success {
        // Get item_count from result (batch size)
        itemCount := uc.extractItemCount(ctx, res.Payload)

        uc.stateUC.IncrementCrawlDoneBy(ctx, projectID, int64(itemCount))
        uc.stateUC.IncrementAnalyzeTotalBy(ctx, projectID, int64(itemCount))
    }
    // ...
}
```

**Flow:**

```
Crawler crawl 50 items
    │
    ├── Upload MinIO
    ├── Publish data.collected (item_count=50)
    └── Return result to Collector (item_count=50)
            │
            └── Collector: crawl_done += 50, analyze_total += 50
```

---

## 8. Configuration

```yaml
# analytics/config.yaml

rabbitmq:
  url: ${RABBITMQ_URL:amqp://guest:guest@localhost:5672/}

  # Input
  consume_exchange: smap.events
  consume_routing_key: data.collected
  consume_queue: analytics.data.collected

  # Output
  publish_exchange: results.inbound
  publish_routing_key: analyze.result

minio:
  endpoint: ${MINIO_ENDPOINT:localhost:9000}
  access_key: ${MINIO_ACCESS_KEY}
  secret_key: ${MINIO_SECRET_KEY}
  bucket: ${MINIO_BUCKET:smap-data}
  use_ssl: false
```

---

## 9. Error Handling

### 9.1. MinIO Fetch Error

```go
func (c *consumer) HandleDataCollected(ctx context.Context, event DataCollectedEvent) error {
    contents, err := c.minioClient.FetchBatch(ctx, event.Payload.MinioPath)
    if err != nil {
        // Publish error result
        errorMsg := AnalyzeResultMessage{
            Success: false,
            Payload: AnalyzeResultPayload{
                ProjectID:  event.Payload.ProjectID,
                JobID:      event.Payload.JobID,
                TaskType:   "analyze_result",
                BatchSize:  event.Payload.ItemCount,
                ErrorCount: event.Payload.ItemCount,  // All items failed
                Errors: []AnalyzeError{{
                    ContentID: "batch",
                    Error:     fmt.Sprintf("MinIO fetch failed: %v", err),
                }},
            },
        }
        return c.publisher.PublishAnalyzeResult(ctx, errorMsg)
    }
    // ...
}
```

### 9.2. Partial Failure

Nếu analyze 50 items, 48 success, 2 failed:

```json
{
  "success": true,
  "payload": {
    "batch_size": 50,
    "success_count": 48,
    "error_count": 2,
    "results": [...],  // 48 items
    "errors": [...]    // 2 items
  }
}
```

Collector sẽ:

- `analyze_done += 48`
- `analyze_errors += 2`

---

## 10. Checklist

### Analytics Service

- [x] Setup RabbitMQ consumer for `data.collected`
- [x] Setup MinIO client
- [x] Implement batch fetch from MinIO
- [x] Implement batch analysis
- [x] Setup RabbitMQ publisher for `analyze.result`
- [x] Include `task_type: "analyze_result"` trong message
- [x] Include `success_count`, `error_count` trong message
- [x] Handle MinIO fetch errors
- [x] Handle partial analysis failures
- [x] Test end-to-end flow

**Implementation Details (2025-12-15):**

- Message types: `models/messages.py` (`AnalyzeResultMessage`, `AnalyzeResultPayload`, `AnalyzeItem`, `AnalyzeError`)
- Publisher: `infrastructure/messaging/publisher.py` (`RabbitMQPublisher`)
- Consumer integration: `internal/consumers/main.py` (`build_result_items()`, `build_error_items()`)
- Entry point: `command/consumer/main.py` (publisher initialization)
- Config: `core/config.py` (`publish_exchange`, `publish_routing_key`, `publish_enabled`)
- Tests: 49 tests passed (`tests/test_models/`, `tests/test_messaging/`, `tests/test_consumers/`)

### Collector Service (cần update)

- [ ] Add `handleAnalyzeResult()` handler
- [ ] Parse `AnalyzePayload` với `success_count`, `error_count`
- [ ] Add `IncrementAnalyzeDoneBy(count)` method
- [ ] Add `IncrementAnalyzeErrorsBy(count)` method
- [ ] Update `handleProjectResult()` để set `analyze_total` từ `item_count`
