# Event-Driven Architecture Implementation Guide

**Last Updated**: 2025-12-07
**Status**: ✅ Production Ready (Analytics, Crawler, Collector Services)

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Event Infrastructure](#event-infrastructure)
4. [Implementation Status](#implementation-status)
5. [Service Integration Details](#service-integration-details)
6. [Event Schemas](#event-schemas)
7. [State Management (Redis)](#state-management-redis)
8. [Progress Notifications](#progress-notifications)
9. [Configuration Guide](#configuration-guide)
10. [Deployment Checklist](#deployment-checklist)

---

## Overview

### Purpose

This document describes the event-driven choreography architecture for the SMAP (Social Media Analytics Platform) system, enabling autonomous data flow from Project creation through Crawling, Analytics, to Dashboard visualization.

### Architecture Goals

- **Autonomous Data Flow**: Services operate independently without direct coupling
- **Scalability**: Horizontal scaling via message queue load distribution
- **Resilience**: Fault isolation and graceful degradation
- **Real-time Updates**: WebSocket-based progress notifications
- **Observability**: Comprehensive monitoring and error tracking

### System Flow

```
Client → Project Service → Collector Service → Crawler Services → Analytics Service → Dashboard
           (PostgreSQL)      (RabbitMQ)         (MinIO)            (PostgreSQL)       (WebSocket)
```

---

## Architecture Principles

### Event Choreography (Not Orchestration)

The system uses **choreography** where each service reacts to events independently, rather than a central orchestrator controlling the flow.

**Benefits**:

- Lower coupling between services
- Independent deployability
- Natural fault isolation
- Easier horizontal scaling

### Message Patterns

1. **Event Publication**: Services publish domain events when state changes occur
2. **Event Consumption**: Services subscribe to relevant events and react autonomously
3. **State Sharing**: Redis used for shared state (progress tracking)
4. **Storage Separation**: MinIO for large payloads, RabbitMQ for event notifications

### Why Batching?

Batch processing (50 posts/batch for TikTok, 20 for YouTube) provides:

- **10x throughput improvement** (98% reduction in message queue load)
- **86% cost reduction** ($4,044/year savings on AWS)
- **Better reliability** (fewer network round-trips, bulk database operations)

Batch sizes: 50 posts/batch for TikTok, 20 for YouTube.

---

## Event Infrastructure

### Exchange Configuration

**Primary Exchange**: `smap.events` (Type: `topic`)

All services publish and consume from this single exchange using routing key patterns for message filtering.

### Routing Keys

| Routing Key         | Producer          | Consumers         | Description                      |
| :------------------ | :---------------- | :---------------- | :------------------------------- |
| `project.created`   | Project Service   | Collector Service | New project execution started    |
| `data.collected`    | Crawler Services  | Analytics Service | Batch data uploaded to MinIO     |
| `analysis.finished` | Analytics Service | Insight Service   | Analytics completed for one post |
| `job.completed`     | Analytics Service | Notification      | Entire project finished          |

### Queue Naming Conventions

Each consumer creates its own queue with a descriptive name:

- `collector.project.created` - Collector's queue for project events
- `analytics.data.collected` - Analytics' queue for data events
- `insights.analysis.finished` - Insights' queue for analysis events

### Message Flow Pattern

```
1. Service performs action (e.g., Crawler uploads batch to MinIO)
2. Service publishes event to smap.events with routing key (e.g., data.collected)
3. Exchange routes message to all queues bound with matching routing key
4. Consumers process message asynchronously
5. Consumers update shared state (Redis) if needed
6. Consumers may publish subsequent events
```

---

## Implementation Status

### Component Completion Matrix

| Service               | Component                       | Status         | Verified   |
| --------------------- | ------------------------------- | -------------- | ---------- |
| **Project Service**   | Exchange Configuration          | ✅ Implemented | 2025-12-05 |
| **Project Service**   | ProjectCreatedEvent Publisher   | ✅ Implemented | 2025-12-05 |
| **Project Service**   | Redis State Initialization      | ✅ Implemented | 2025-12-05 |
| **Project Service**   | Progress Webhook Handler        | ✅ Implemented | 2025-12-05 |
| **Collector Service** | Exchange Configuration          | ✅ Implemented | 2025-12-06 |
| **Collector Service** | ProjectCreatedEvent Consumer    | ✅ Implemented | 2025-12-06 |
| **Collector Service** | Redis State Management          | ✅ Implemented | 2025-12-06 |
| **Collector Service** | Progress Webhook Client         | ✅ Implemented | 2025-12-06 |
| **Collector Service** | User Mapping Storage            | ✅ Implemented | 2025-12-06 |
| **Collector Service** | Task Type Differentiation       | ✅ Implemented | 2025-12-06 |
| **Collector Service** | Dry-Run Result Handler          | ✅ Implemented | 2025-12-06 |
| **Collector Service** | Project Result Handler          | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | TaskType in Result Metadata     | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | DataCollectedEvent Publisher    | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | Batch Upload to MinIO           | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | Enhanced Error Reporting        | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | Configuration Externalization   | ✅ Implemented | 2025-12-06 |
| **Crawler Services**  | Retry Logic with Backoff        | ✅ Implemented | 2025-12-06 |
| **Analytics Service** | DataCollectedEvent Consumer     | ✅ Implemented | 2025-12-07 |
| **Analytics Service** | Batch Processing                | ✅ Implemented | 2025-12-07 |
| **Analytics Service** | Error Handling & Categorization | ✅ Implemented | 2025-12-07 |
| **Analytics Service** | Project ID Extraction           | ✅ Implemented | 2025-12-07 |
| **Analytics Service** | Prometheus Metrics              | ✅ Implemented | 2025-12-07 |
| **Analytics Service** | Database Schema Extensions      | ✅ Implemented | 2025-12-07 |
| **WebSocket Service** | Redis Pub/Sub Subscriber        | ⏳ Pending     | -          |

### Verification References

- **Crawler Service**: `openspec/changes/archive/refactor-crawler-event-integration/`
- **Collector Service**: `openspec/changes/archive/review-event-driven-compliance/`
- **Analytics Service**: `openspec/changes/archive/integrate-crawler-events/` + `openspec/changes/archive/fix-batch-processing-issues/`

---

## Service Integration Details

### 1. Project Service

**Responsibilities**:

- Manage project lifecycle (creation, execution, completion)
- Initialize Redis state for progress tracking
- Publish `project.created` events
- Handle progress webhook callbacks
- Publish WebSocket notifications via Redis Pub/Sub

#### API Endpoints

**Public Endpoints** (Cookie Authentication):

| Method | Endpoint                 | Description                     |
| ------ | ------------------------ | ------------------------------- |
| POST   | `/projects`              | Create project (PostgreSQL)     |
| POST   | `/projects/:id/execute`  | Start execution (Redis + Event) |
| GET    | `/projects/:id/progress` | Get progress (Redis)            |
| POST   | `/projects/dryrun`       | Start dry-run test              |

**Internal Endpoints** (X-Internal-Key Authentication):

| Method | Endpoint                      | Description                    |
| ------ | ----------------------------- | ------------------------------ |
| POST   | `/internal/progress/callback` | Progress update from Collector |
| POST   | `/internal/dryrun/callback`   | Dry-run result from Collector  |

#### Execute Flow (POST /projects/:id/execute)

```go
func (u *projectUseCase) Execute(ctx context.Context, projectID, userID string) error {
    // 1. Get project from PostgreSQL
    project, err := u.repo.GetByID(ctx, projectID)
    if err != nil {
        return err
    }

    // 2. Authorization check
    if project.CreatedBy != userID {
        return ErrUnauthorized
    }

    // 3. Prevent duplicate execution
    state, _ := u.stateUC.GetState(ctx, projectID)
    if state != nil && state.Status == "CRAWLING" {
        return ErrProjectAlreadyExecuting
    }

    // 4. Initialize Redis state
    if err := u.stateUC.InitState(ctx, projectID); err != nil {
        return err
    }

    // 5. Publish project.created event
    event := ToProjectCreatedEvent(project, userID)
    return u.eventPublisher.PublishProjectCreated(ctx, event)
}
```

**Key Design Decision**: Execute is separate from Create to allow dry-run testing before full execution.

---

### 2. Collector Service

**Responsibilities**:

- Consume `project.created` events
- Dispatch crawler jobs (brand + competitors)
- Update Redis state (total, done, errors)
- Call progress webhook (throttled)
- Store project_id → user_id mapping
- Route results based on task_type

#### Event Consumption

```python
# Queue: collector.project.created
# Exchange: smap.events
# Routing Key: project.created

def handle_project_created(event):
    payload = event['payload']

    project_id = payload['project_id']
    user_id = payload['user_id']  # For progress notifications
    brand_keywords = payload['brand_keywords']
    competitor_keywords_map = payload['competitor_keywords_map']
    date_range = payload['date_range']

    # Store mapping for later callbacks
    store_project_user_mapping(project_id, user_id)

    # Dispatch crawlers
    dispatch_crawlers(project_id, brand_keywords, competitor_keywords_map, date_range)
```

#### Redis State Updates

```python
def update_project_state(project_id, field, value):
    key = f"smap:proj:{project_id}"

    if field == "total":
        redis.hset(key, "total", value)
        redis.hset(key, "status", "CRAWLING")
    elif field == "done":
        redis.hincrby(key, "done", 1)
    elif field == "errors":
        redis.hincrby(key, "errors", 1)
    elif field == "status":
        redis.hset(key, "status", value)
```

#### Progress Webhook (Throttled)

```python
# Throttle to minimum 5 seconds between calls
THROTTLE_INTERVAL = 5  # seconds
last_notify_time = {}

def should_notify(project_id):
    now = time.time()
    last = last_notify_time.get(project_id, 0)
    if now - last > THROTTLE_INTERVAL:
        last_notify_time[project_id] = now
        return True
    return False

def on_item_crawled(project_id, user_id, is_error=False):
    # Always update Redis
    if is_error:
        update_project_state(project_id, "errors", 1)
    update_project_state(project_id, "done", 1)

    # Throttle webhook calls
    if should_notify(project_id):
        notify_progress(project_id, user_id)
```

#### Task Type Differentiation

```go
// internal/results/usecase/result.go

func (uc implUseCase) HandleResult(ctx context.Context, res models.CrawlerResult) error {
    taskType := uc.extractTaskType(ctx, res.Payload)

    switch taskType {
    case "dryrun_keyword":
        return uc.handleDryRunResult(ctx, res)      // → /internal/dryrun/callback
    case "research_and_crawl":
        return uc.handleProjectResult(ctx, res)     // → Update Redis + /internal/progress/callback
    default:
        return uc.handleDryRunResult(ctx, res)      // Backward compatibility
    }
}
```

---

### 3. Crawler Services (TikTok, YouTube)

**Responsibilities**:

- Crawl content based on keywords and date range
- Batch results (50 TikTok, 20 YouTube)
- Upload batches to MinIO
- Publish `data.collected` events
- Include task_type in metadata
- Enhanced error reporting (17 error codes)

#### Batch Upload Implementation

```python
# tiktok/application/crawler_service.py

BATCH_SIZE = 50  # TikTok batch size

def process_crawl_results(self, job_id, results):
    batch = []

    for item in results:
        batch.append(item)

        # Flush batch when full
        if len(batch) >= BATCH_SIZE:
            self.upload_and_publish_batch(job_id, batch)
            batch = []

    # Flush remaining items
    if batch:
        self.upload_and_publish_batch(job_id, batch)

def upload_and_publish_batch(self, job_id, batch):
    # 1. Upload to MinIO
    minio_path = f"crawl-results/tiktok/{project_id}/{type}/batch_{index:03d}.json"
    self.minio_client.upload(minio_path, json.dumps(batch))

    # 2. Publish event
    event = {
        "event_id": generate_event_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "minio_path": minio_path,
            "project_id": extract_project_id(job_id),
            "job_id": job_id,
            "batch_index": index,
            "content_count": len(batch),
            "platform": "tiktok",
            "task_type": self.task_type,
        }
    }
    self.event_publisher.publish("data.collected", event)
```

#### Error Code Mapping

17 error codes across 7 categories:

| Category      | Error Codes                                                |
| ------------- | ---------------------------------------------------------- |
| rate_limiting | RATE_LIMITED, AUTH_FAILED, ACCESS_DENIED                   |
| content       | CONTENT_REMOVED, CONTENT_NOT_FOUND, CONTENT_UNAVAILABLE    |
| network       | NETWORK_ERROR, TIMEOUT, CONNECTION_REFUSED, DNS_ERROR      |
| parsing       | PARSE_ERROR, INVALID_URL, INVALID_RESPONSE                 |
| media         | MEDIA_DOWNLOAD_FAILED, MEDIA_TOO_LARGE, MEDIA_FORMAT_ERROR |
| storage       | STORAGE_ERROR, UPLOAD_FAILED, DATABASE_ERROR               |
| generic       | UNKNOWN_ERROR, INTERNAL_ERROR                              |

Error items are included in batch with `fetch_status: "error"` and detailed error information.

---

### 4. Analytics Service

**Responsibilities**:

- Consume `data.collected` events
- Download batches from MinIO
- Process items (sentiment, intent, impact)
- Extract project_id from job_id
- Handle error items gracefully
- Persist results to PostgreSQL
- Expose Prometheus metrics

For detailed Analytics Service behavior, see [Analytics Service Behavior Specification](analytics-service-behavior.md).

#### Event Consumption

```python
# Queue: analytics.data.collected
# Exchange: smap.events
# Routing Key: data.collected

def handle_data_collected(envelope):
    payload = envelope['payload']

    # Download batch from MinIO
    batch_data = minio_client.download(payload['minio_path'])
    batch_items = json.loads(batch_data)

    # Extract project_id
    project_id = extract_project_id(payload['job_id'])

    # Process each item
    for item in batch_items:
        if item['fetch_status'] == 'success':
            # Run analytics pipeline
            analytics_result = process_analytics(item)
            analytics_result['project_id'] = project_id
            analytics_result['job_id'] = payload['job_id']
            analytics_result['batch_index'] = payload['batch_index']
            save_to_post_analytics(analytics_result)
        else:
            # Save error record
            error_record = extract_error_info(item)
            error_record['project_id'] = project_id
            save_to_crawl_errors(error_record)

    # Acknowledge message
    channel.basic_ack(delivery_tag)
```

---

## Event Schemas

### 1. project.created Event

**Publisher**: Project Service
**Consumers**: Collector Service

```json
{
  "event_id": "evt_abc123",
  "timestamp": "2025-12-05T10:00:00Z",
  "payload": {
    "project_id": "proj_xyz",
    "user_id": "user_123",
    "brand_name": "VinFast",
    "brand_keywords": ["VinFast", "VF3", "VF8"],
    "competitor_names": ["Toyota", "Honda"],
    "competitor_keywords_map": {
      "Toyota": ["Toyota", "Vios", "Camry"],
      "Honda": ["Honda", "City", "Civic"]
    },
    "date_range": {
      "from": "2025-01-01",
      "to": "2025-02-01"
    }
  }
}
```

**Key Fields**:

- `user_id`: Required for progress notifications
- `competitor_keywords_map`: Map of competitor name to keywords
- `date_range`: ISO 8601 date strings (YYYY-MM-DD)

---

### 2. data.collected Event

**Publishers**: Crawler Services (TikTok, YouTube)
**Consumers**: Analytics Service

```json
{
  "event_id": "evt_def456",
  "timestamp": "2025-12-06T10:15:30Z",
  "payload": {
    "minio_path": "crawl-results/tiktok/proj_xyz/brand/batch_001.json",
    "project_id": "proj_xyz",
    "job_id": "proj_xyz-brand-0",
    "batch_index": 1,
    "content_count": 50,
    "platform": "tiktok",
    "task_type": "research_and_crawl",
    "keyword": "VinFast VF8"
  }
}
```

**Key Fields**:

- `minio_path`: Full path to batch data in MinIO
- `project_id`: Extracted from job_id (null for dry-run)
- `task_type`: "dryrun_keyword" or "research_and_crawl"
- `content_count`: Number of items in batch

---

### 3. analysis.finished Event (Future)

**Publisher**: Analytics Service
**Consumers**: Insight Service

```json
{
  "event_id": "evt_ghi789",
  "timestamp": "2025-12-06T10:16:00Z",
  "payload": {
    "content_id": "7441234567890123456",
    "project_id": "proj_xyz",
    "platform": "tiktok",
    "sentiment": "positive",
    "intent": "praise",
    "impact_score": 8.5,
    "risk_level": "low"
  }
}
```

---

### 4. job.completed Event (Future)

**Publisher**: Analytics Service
**Consumers**: Notification Service

```json
{
  "event_id": "evt_jkl012",
  "timestamp": "2025-12-06T12:00:00Z",
  "payload": {
    "project_id": "proj_xyz",
    "total_items": 1000,
    "successful_items": 950,
    "failed_items": 50,
    "completion_time": "2025-12-06T12:00:00Z"
  }
}
```

---

## State Management (Redis)

### Database Selection

- **DB 0**: Job mapping, Pub/Sub (mainRedisClient)
- **DB 1**: Project state tracking (stateRedisClient)

### Key Schema

```
smap:proj:{projectID}
```

### Hash Fields

| Field    | Type   | Description              | Writer            |
| :------- | :----- | :----------------------- | :---------------- |
| `status` | String | Project execution status | Project/Collector |
| `total`  | Int    | Total items to process   | Collector         |
| `done`   | Int    | Items completed          | Collector         |
| `errors` | Int    | Items failed             | Collector         |

### Status Constants

```go
// internal/model/state.go

type ProjectStatus string

const (
    ProjectStatusInitializing ProjectStatus = "INITIALIZING"
    ProjectStatusCrawling     ProjectStatus = "CRAWLING"
    ProjectStatusProcessing   ProjectStatus = "PROCESSING"
    ProjectStatusDone         ProjectStatus = "DONE"
    ProjectStatusFailed       ProjectStatus = "FAILED"
)
```

### State Initialization (Project Service)

```go
// When user calls POST /projects/:id/execute
key := fmt.Sprintf("smap:proj:%s", projectID)

pipe := redis.Pipeline()
pipe.HSet(key, "status", "INITIALIZING")
pipe.HSet(key, "total", "0")
pipe.HSet(key, "done", "0")
pipe.HSet(key, "errors", "0")
pipe.Expire(key, 7 * 24 * time.Hour)  // 7 days TTL
pipe.Exec()
```

### State Update Triggers

| Event             | Redis Update                                 | Webhook Call |
| ----------------- | -------------------------------------------- | ------------ |
| Found total items | `HSET total {count}`, `HSET status CRAWLING` | Immediate    |
| Crawled 1 item    | `HINCRBY done 1`                             | Throttled    |
| Item failed       | `HINCRBY errors 1`                           | Throttled    |
| All done          | `HSET status DONE`                           | Immediate    |
| Fatal error       | `HSET status FAILED`                         | Immediate    |

---

## Progress Notifications

### Webhook Endpoint

**URL**: `POST /internal/progress/callback`
**Authentication**: `X-Internal-Key` header

### Request Schema

```json
{
  "project_id": "proj_xyz",
  "user_id": "user_123",
  "status": "CRAWLING",
  "total": 1000,
  "done": 150,
  "errors": 2
}
```

### Project Service Handler

```go
func (uc *usecase) HandleProgressCallback(ctx context.Context, req ProgressCallbackRequest) error {
    channel := fmt.Sprintf("user_noti:%s", req.UserID)

    // Calculate progress
    var progressPercent float64
    if req.Total > 0 {
        progressPercent = float64(req.Done) / float64(req.Total) * 100
    }

    // Determine message type
    messageType := MessageTypeProjectProgress
    if req.Status == "DONE" || req.Status == "FAILED" {
        messageType = MessageTypeProjectCompleted
    }

    // Publish to Redis Pub/Sub
    message := map[string]interface{}{
        "type": messageType,
        "payload": map[string]interface{}{
            "project_id":       req.ProjectID,
            "status":           req.Status,
            "total":            req.Total,
            "done":             req.Done,
            "errors":           req.Errors,
            "progress_percent": progressPercent,
        },
    }

    return uc.redisClient.Publish(ctx, channel, message)
}
```

### WebSocket Message Types

**Progress Update**:

```json
{
  "type": "project_progress",
  "payload": {
    "project_id": "proj_xyz",
    "status": "CRAWLING",
    "total": 1000,
    "done": 150,
    "errors": 2,
    "progress_percent": 15.0
  }
}
```

**Completion**:

```json
{
  "type": "project_completed",
  "payload": {
    "project_id": "proj_xyz",
    "status": "DONE",
    "total": 1000,
    "done": 1000,
    "errors": 5,
    "progress_percent": 100.0
  }
}
```

### Redis Pub/Sub Channel

```
user_noti:{user_id}
```

WebSocket Service (pending implementation) will subscribe to this channel and forward messages to connected clients.

---

## Configuration Guide

### Project Service

```env
# Redis
REDIS_HOST=localhost:6379
REDIS_STATE_DB=1

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Internal API
INTERNAL_KEY=your-secure-internal-key
```

### Collector Service

```env
# Project Service
PROJECT_SERVICE_URL=http://project-service:8080
PROJECT_INTERNAL_KEY=your-secure-internal-key

# Redis (same instance as Project Service)
REDIS_HOST=localhost:6379
REDIS_STATE_DB=1

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

### Crawler Services

```env
# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_CRAWL_RESULTS_BUCKET=crawl-results

# Event Publisher
EVENT_EXCHANGE_NAME=smap.events
EVENT_ROUTING_KEY=data.collected
EVENT_PUBLISHER_ENABLED=true

# Batch Configuration
BATCH_SIZE_TIKTOK=50
BATCH_SIZE_YOUTUBE=20

# Metadata
PIPELINE_VERSION=crawler_tiktok_v3
DEFAULT_LANG=vi
DEFAULT_REGION=VN
```

### Analytics Service

```env
# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
EVENT_EXCHANGE=smap.events
EVENT_ROUTING_KEY=data.collected
EVENT_QUEUE_NAME=analytics.data.collected

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_CRAWL_RESULTS_BUCKET=crawl-results

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/analytics

# Processing
MAX_CONCURRENT_BATCHES=5
BATCH_TIMEOUT_SECONDS=30

# Metrics
PROMETHEUS_PORT=9090
```

---

## Deployment Checklist

### Project Service

- [ ] RabbitMQ connection configured
- [ ] Redis DB 1 connection configured
- [ ] Event publisher enabled
- [ ] Progress webhook endpoint secured with internal key
- [ ] WebSocket Pub/Sub configured

### Collector Service

- [ ] RabbitMQ connection configured
- [ ] Queue `collector.project.created` declared
- [ ] Exchange binding to `smap.events` with `project.created`
- [ ] Redis DB 1 connection configured
- [ ] Project Service webhook URL configured
- [ ] Internal key configured
- [ ] User mapping storage implemented
- [ ] Task type routing logic implemented

### Crawler Services

- [ ] RabbitMQ connection configured
- [ ] MinIO connection configured
- [ ] Event publisher enabled
- [ ] Batch sizes configured (50 TikTok, 20 YouTube)
- [ ] task_type included in metadata
- [ ] Error codes mapped to categories
- [ ] Retry logic with exponential backoff
- [ ] Pipeline version configured

### Analytics Service

- [ ] RabbitMQ connection configured
- [ ] Queue `analytics.data.collected` declared
- [ ] Exchange binding to `smap.events` with `data.collected`
- [ ] MinIO connection configured
- [ ] PostgreSQL connection configured
- [ ] Database migrations applied
- [ ] Prometheus metrics exposed on port 9090
- [ ] Batch processing enabled
- [ ] Error handling configured

### Infrastructure

- [ ] RabbitMQ cluster healthy
- [ ] Redis instances healthy (DB 0, DB 1)
- [ ] MinIO cluster healthy
- [ ] PostgreSQL instances healthy
- [ ] Monitoring configured (Prometheus, Grafana)
- [ ] Logging aggregation configured (ELK, CloudWatch)

---

## Sequence Diagram

```
Client          Project         Collector       Crawler         Analytics       Redis           WebSocket
  |                |                |              |                |              |                |
  | POST /execute  |                |              |                |              |                |
  |--------------->|                |              |                |              |                |
  |                |                |              |                |              |                |
  |                | Init state     |              |                |              |                |
  |                |--------------------------------------------------------------------->|                |
  |                |                |              |                |              |                |
  |                | Publish project.created       |                |              |                |
  |                |--------------->|              |                |              |                |
  |                |                |              |                |              |                |
  |  200 OK        |                |              |                |              |                |
  |<---------------|                |              |                |              |                |
  |                |                |              |                |              |                |
  |                |                | Dispatch job |                |              |                |
  |                |                |------------->|                |              |                |
  |                |                |              |                |              |                |
  |                |                |              | Upload batch   |              |                |
  |                |                |              |--------------->MinIO          |                |
  |                |                |              |                |              |                |
  |                |                |              | Publish data.collected         |                |
  |                |                |              |--------------->|              |                |
  |                |                |              |                |              |                |
  |                |                |              |                | Download batch from MinIO     |
  |                |                |              |                |              |                |
  |                |                |              |                | Process items|                |
  |                |                |              |                |              |                |
  |                |                |              |                | Save to PostgreSQL            |
  |                |                |              |                |              |                |
  |                |                | Update state |                |              |                |
  |                |                |----------------------------------------------------->|                |
  |                |                |              |                |              |                |
  |                | POST /progress/callback       |                |              |                |
  |                |<---------------|              |                |              |                |
  |                |                |              |                |              |                |
  |                | Publish user_noti:{user_id}   |                |              |                |
  |                |--------------------------------------------------------------------->|                |
  |                |                |              |                |              |                |
  |                |                |              |                |              | Subscribe      |
  |                |                |              |                |              |<---------------|
  |                |                |              |                |              |                |
  |                |                |              |                |              | Message        |
  |                |                |              |                |              |--------------->|
  |                |                |              |                |              |                |
  | WebSocket message                                                                               |
  |<-------------------------------------------------------------------------------------------------|
  |                |                |              |                |              |                |
```

---

## Related Documentation

- [Analytics Service Behavior Specification](analytics-service-behavior.md) - Detailed Analytics Service behavior
- [Batch Processing Rationale](batch-processing-rationale.md) - Technical justification for batching
- [Integration Contract](integration-contract.md) - Crawler-Analytics interface specification
- [Analytics Service Integration Guide](analytics-service-integration-guide.md) - Integration instructions
- [Architecture Overview](architecture.md) - System architecture and design patterns
