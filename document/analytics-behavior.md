# Analytics Service Behavior Specification

**Last Updated**: 2025-12-15
**Status**: ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Event Consumption](#event-consumption)
4. [Batch Processing](#batch-processing)
5. [Result Publishing](#result-publishing)
6. [Project ID Extraction](#project-id-extraction)
7. [Error Handling](#error-handling)
8. [Database Schema](#database-schema)
9. [Configuration](#configuration)
10. [Performance Characteristics](#performance-characteristics)
11. [Migration Status](#migration-status)

---

## Overview

Analytics Service is a microservice in the SMAP event-driven architecture responsible for processing and analyzing social media data from crawler services (TikTok, YouTube).

### Service Responsibilities

- **Event Consumption**: Listen to `data.collected` events from RabbitMQ
- **Batch Processing**: Download and process batches of crawled content from MinIO
- **Analytics Pipeline**: Execute sentiment analysis, intent classification, and impact calculation
- **Error Management**: Handle and categorize crawler errors for monitoring
- **Data Persistence**: Store analytics results and error records in PostgreSQL
- **Result Publishing**: Publish analyze results back to Collector Service via RabbitMQ

### Key Characteristics

- **Asynchronous Processing**: Event-driven, message queue based
- **Batch-Oriented**: Processes items in batches for optimal performance
- **Resilient**: Per-item error handling prevents batch failures
- **Scalable**: Horizontal scaling via multiple consumer instances

---

## Architecture

### System Context

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Crawler        │     │   RabbitMQ      │     │   Analytics     │     │   RabbitMQ      │
│  Services       │────▶│   smap.events   │────▶│   Service       │────▶│ results.inbound │
│  (TikTok/YT)    │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │                       │
        ▼                                               ▼                       ▼
┌─────────────────┐                           ┌─────────────────┐     ┌─────────────────┐
│     MinIO       │◀──────────────────────────│   PostgreSQL    │     │   Collector     │
│  crawl-results  │                           │  post_analytics │     │   Service       │
└─────────────────┘                           └─────────────────┘     └─────────────────┘
```

### Data Flow

1. **Crawler** uploads batch data to MinIO
2. **Crawler** publishes `data.collected` event to RabbitMQ
3. **Analytics Service** receives event from queue
4. **Analytics Service** downloads batch from MinIO
5. **Analytics Service** processes each item (analytics pipeline)
6. **Analytics Service** persists results to PostgreSQL
7. **Analytics Service** publishes `analyze.result` to Collector Service
8. **Analytics Service** acknowledges message

---

## Event Consumption

### Queue Configuration

- **Exchange**: `smap.events` (topic)
- **Routing Key**: `data.collected`
- **Queue Name**: `analytics.data.collected`
- **Binding**: Queue binds to exchange with routing key pattern

### Event Schema

Analytics Service consumes `data.collected` events with the following structure:

```json
{
  "event_id": "evt_abc123",
  "event_type": "data.collected",
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

### Event Validation

The service validates incoming events before processing:

```python
def validate_event_format(envelope: dict) -> bool:
    """Validate that envelope is a valid data.collected event."""
    if "payload" not in envelope:
        return False

    payload = envelope["payload"]
    required_fields = ["minio_path", "job_id", "platform", "content_count"]

    return all(field in payload for field in required_fields)
```

### Message Acknowledgment

- **Success**: Message is acked after successful batch processing
- **Partial Failure**: Message is acked even if some items fail (graceful error handling)
- **Infrastructure Failure**: Message is nacked and requeued (e.g., database down, MinIO unreachable)

---

## Batch Processing

> **Why Batching?** Batch processing provides 10x throughput improvement, 86% cost reduction, and better reliability. See [Batch Processing Rationale](batch-processing-rationale.md) for detailed technical justification.

### Processing Flow

```
1. Receive Event
   ↓
2. Validate Event Format
   ↓
3. Extract Metadata (project_id, job_id, platform)
   ↓
4. Download Batch from MinIO
   ↓
5. Parse Batch JSON
   ↓
6. Extract Project ID from job_id
   ↓
7. For Each Item in Batch:
   ├─ Check fetch_status
   ├─ If "success" → Run Analytics Pipeline
   ├─ If "error" → Save to crawl_errors
   └─ Enrich with batch context
   ↓
8. Bulk Insert to Database
   ↓
9. Publish Results to Collector (analyze.result)
   ↓
10. Log Statistics
   ↓
11. Acknowledge Message
```

### Batch Size Expectations

| Platform | Expected Batch Size | Rationale                        |
| -------- | ------------------- | -------------------------------- |
| TikTok   | 50 items            | Balances API limits & throughput |
| YouTube  | 20 items            | Lower rate limits                |

**Note**: The service logs a warning if actual batch size differs from expected, but continues processing. A Prometheus metric `analytics_batch_size_mismatch_total` tracks these occurrences.

### Per-Item Processing Logic

Each item in a batch is processed independently to ensure fault isolation:

#### Success Items (`fetch_status: "success"`)

1. **Sentiment Analysis**: Analyze overall sentiment and aspect-based sentiment
2. **Intent Classification**: Classify user intent (question, complaint, praise, etc.)
3. **Impact Calculation**: Calculate impact score and risk level
4. **Context Enrichment**: Add batch metadata (job_id, batch_index, task_type)
5. **Database Insert**: Save to `post_analytics` table

#### Error Items (`fetch_status: "error"`)

1. **Error Detection**: Identify items with fetch_status="error"
2. **Error Extraction**: Parse error_code, error_message, error_details
3. **Error Categorization**: Map error_code to error_category
4. **Database Insert**: Save to `crawl_errors` table
5. **Logging**: Log warning with context (does not crash batch)

### Batch Context Enrichment

All items are enriched with batch-level metadata:

```python
item_enrichment = {
    "job_id": payload["job_id"],
    "batch_index": payload["batch_index"],
    "task_type": payload.get("task_type"),
    "keyword_source": payload.get("keyword"),
    "crawled_at": parse_timestamp(envelope["timestamp"]),
    "pipeline_version": detect_pipeline_version(platform),
}
```

---

## Result Publishing

After processing a batch, Analytics Service publishes results back to Collector Service via RabbitMQ. This enables the Collector to track analysis progress and notify projects via webhooks.

### Publisher Configuration

| Setting     | Value             | Description                      |
| ----------- | ----------------- | -------------------------------- |
| Exchange    | `results.inbound` | Exchange for result messages     |
| Routing Key | `analyze.result`  | Routing key for analyze results  |
| Queue       | Collector-managed | Collector binds its own queue    |
| Enabled     | `PUBLISH_ENABLED` | Feature flag for gradual rollout |

### Result Message Schema

Analytics publishes **1 message per batch** (not per item):

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

### Message Types

The result publishing system uses flat JSON format (defined in `models/messages.py`):

```python
@dataclass
class AnalyzeResultPayload:
    """Flat payload for Collector consumption.

    Message format follows collector-crawler-contract.md Section 3.
    Published as flat JSON with 6 fields only.
    """
    project_id: str  # Required, non-empty
    job_id: str
    task_type: str = "analyze_result"
    batch_size: int = 0
    success_count: int = 0
    error_count: int = 0
```

### Message Format

Analytics publishes **flat JSON** directly to Collector (no wrapper):

```json
{
  "project_id": "proj_xyz",
  "job_id": "proj_xyz-brand-0",
  "task_type": "analyze_result",
  "batch_size": 50,
  "success_count": 48,
  "error_count": 2
}
```

### Publishing Flow

```
1. Batch Processing Complete
   ↓
2. Validate project_id (skip if empty)
   ↓
3. Create AnalyzeResultPayload (flat)
   ↓
4. Serialize to JSON
   ↓
5. Publish to results.inbound exchange
   ↓
6. Log success/failure
```

### Result Scenarios

| Scenario            | `success_count` | `error_count` | Description                 |
| ------------------- | --------------- | ------------- | --------------------------- |
| All items succeeded | N               | 0             | Full batch success          |
| Partial failure     | N-M             | M             | Some items failed           |
| MinIO fetch failed  | 0               | N             | Entire batch failed         |
| All items failed    | 0               | N             | All individual items failed |

### Error Result Publishing

When MinIO fetch fails, Analytics publishes an error result:

```json
{
  "project_id": "proj_xyz",
  "job_id": "proj_xyz-brand-0",
  "task_type": "analyze_result",
  "batch_size": 50,
  "success_count": 0,
  "error_count": 50
}
```

> **Note**: Error details are logged internally but not included in the published message.
> Collector only needs counts to track progress.

### Publish Failure Handling

Publishing failures are handled gracefully:

- **Log Error**: Error is logged with full context
- **Continue Processing**: Consumer continues (doesn't block)
- **No Retry**: Failed publishes are not retried (fire-and-forget)
- **Metrics**: `analytics_publish_errors_total` counter incremented

```python
try:
    publisher.publish_analyze_result(result_message)
    logger.info("Published analyze result", extra={"job_id": job_id})
except Exception as e:
    logger.error("Failed to publish analyze result", extra={
        "job_id": job_id,
        "error": str(e)
    })
    # Continue processing - don't block consumer
```

### Publisher Lifecycle

The `RabbitMQPublisher` is initialized once at consumer startup:

```python
# command/consumer/main.py
async def main():
    # 1. Create shared channel
    channel = await connection.channel()

    # 2. Initialize publisher with shared channel
    publisher = RabbitMQPublisher(channel, settings)

    # 3. Setup exchange declaration
    await publisher.setup()

    # 4. Pass publisher to message handler
    handler = create_message_handler(publisher=publisher)

    # 5. Start consuming
    await consumer.consume(handler)
```

### Implementation Files

| File                                    | Description                              |
| --------------------------------------- | ---------------------------------------- |
| `models/messages.py`                    | Message dataclasses and serialization    |
| `infrastructure/messaging/publisher.py` | RabbitMQPublisher class                  |
| `internal/consumers/main.py`            | Handler integration and helper functions |
| `command/consumer/main.py`              | Publisher initialization                 |
| `core/config.py`                        | Publisher configuration settings         |

---

## Project ID Extraction

### Purpose

The `project_id` field links analytics results to projects in the Project Service. It enables:

- Project-level analytics aggregation
- Dashboard queries filtered by project
- User permission enforcement

### Job ID Patterns

The service extracts `project_id` from `job_id` using pattern matching:

| Job ID Format  | Example                                | Extracted project_id | Task Type            |
| -------------- | -------------------------------------- | -------------------- | -------------------- |
| Brand          | `proj_xyz-brand-0`                     | `proj_xyz`           | Project execution    |
| Competitor     | `proj_xyz-toyota-5`                    | `proj_xyz`           | Project execution    |
| Complex        | `my-project-name-competitor-10`        | `my-project-name`    | Project execution    |
| Dry-run (UUID) | `550e8400-e29b-41d4-a716-446655440000` | `null`               | Dry-run keyword test |

### Extraction Algorithm

```python
def extract_project_id(job_id: str) -> Optional[str]:
    """
    Extract project_id from job_id.

    Returns None for dry-run tasks (UUID format).
    Returns project_id for brand/competitor tasks.
    """
    # UUID pattern → dry-run → None
    if UUID_PATTERN.match(job_id):
        return None

    # Split by hyphen
    parts = job_id.split("-")

    # Require at least: {project}-{type}-{index}
    if len(parts) < 3:
        return None

    # Last part must be numeric index
    if not parts[-1].isdigit():
        return None

    # project_id = everything except last 2 parts (type, index)
    return "-".join(parts[:-2])
```

### Test Coverage

The extraction logic is thoroughly tested with 22 test cases covering:

- Valid brand formats
- Valid competitor formats
- UUID dry-run formats
- Edge cases (missing hyphens, non-numeric index, etc.)

See `tests/test_utils/test_project_id_extractor.py` for full test suite.

---

## Error Handling

### Error Categories

Analytics Service categorizes errors into 7 categories for monitoring and alerting:

| Category      | Error Codes                                                | Retryable? | Description                   |
| ------------- | ---------------------------------------------------------- | ---------- | ----------------------------- |
| rate_limiting | RATE_LIMITED, AUTH_FAILED, ACCESS_DENIED                   | Yes        | Platform API rate limits      |
| content       | CONTENT_REMOVED, CONTENT_NOT_FOUND, CONTENT_UNAVAILABLE    | No         | Content deleted or private    |
| network       | NETWORK_ERROR, TIMEOUT, CONNECTION_REFUSED, DNS_ERROR      | Yes        | Network infrastructure issues |
| parsing       | PARSE_ERROR, INVALID_URL, INVALID_RESPONSE                 | No         | Data format issues            |
| media         | MEDIA_DOWNLOAD_FAILED, MEDIA_TOO_LARGE, MEDIA_FORMAT_ERROR | No         | Media processing failures     |
| storage       | STORAGE_ERROR, UPLOAD_FAILED, DATABASE_ERROR               | Yes        | Storage infrastructure issues |
| generic       | UNKNOWN_ERROR, INTERNAL_ERROR                              | Maybe      | Unclassified errors           |

### Graceful Degradation

The service implements graceful error handling to maximize reliability:

- **Per-Item Isolation**: Item failures do NOT crash entire batch
- **Error Persistence**: Error items are logged and saved to `crawl_errors` table
- **Batch Completion**: Batch is acknowledged after processing all items (including errors)
- **Metrics Tracking**: Error distribution is tracked via Prometheus metrics

### Error Record Schema

Error items are saved with full context for debugging:

```json
{
  "content_id": "7441234567890123456",
  "project_id": "proj_xyz",
  "job_id": "proj_xyz-brand-0",
  "platform": "tiktok",
  "error_code": "CONTENT_NOT_FOUND",
  "error_category": "content",
  "error_message": "Video has been deleted by author",
  "error_details": {
    "status_code": 404,
    "response_body": "..."
  },
  "permalink": "https://tiktok.com/@user/video/123",
  "created_at": "2025-12-07T10:15:30Z"
}
```

---

## Database Schema

### post_analytics Table (Extended)

The `post_analytics` table was extended with crawler integration fields:

```sql
-- Original analytics fields (unchanged)
id VARCHAR(50) PRIMARY KEY,
platform VARCHAR(20) NOT NULL,
published_at TIMESTAMP NOT NULL,
analyzed_at TIMESTAMP DEFAULT NOW(),
overall_sentiment VARCHAR(10) NOT NULL,
primary_intent VARCHAR(20) NOT NULL,
impact_score FLOAT NOT NULL,
risk_level VARCHAR(10) NOT NULL,
-- ... (analytics JSONB fields)

-- NEW: Batch context fields
job_id VARCHAR(100),
batch_index INTEGER,
task_type VARCHAR(30),

-- NEW: Crawler metadata fields
keyword_source VARCHAR(200),
crawled_at TIMESTAMP,
pipeline_version VARCHAR(50),

-- NEW: Error tracking fields
fetch_status VARCHAR(10) DEFAULT 'success',
fetch_error TEXT,
error_code VARCHAR(50),
error_details JSONB,

-- NEW: Project reference
project_id UUID
```

#### Key Indexes

```sql
CREATE INDEX idx_post_analytics_project_id ON post_analytics (project_id);
CREATE INDEX idx_post_analytics_job_id ON post_analytics (job_id);
CREATE INDEX idx_post_analytics_fetch_status ON post_analytics (fetch_status);
CREATE INDEX idx_post_analytics_task_type ON post_analytics (task_type);
CREATE INDEX idx_post_analytics_error_code ON post_analytics (error_code);
```

### crawl_errors Table (New)

A dedicated table for error analytics and monitoring:

```sql
CREATE TABLE crawl_errors (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(50) NOT NULL,
    project_id UUID,
    job_id VARCHAR(100) NOT NULL,
    platform VARCHAR(20) NOT NULL,

    -- Error classification
    error_code VARCHAR(50) NOT NULL,
    error_category VARCHAR(30) NOT NULL,
    error_message TEXT,
    error_details JSONB,

    -- Content reference
    permalink TEXT,

    -- Timestamp
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_crawl_errors_project_id ON crawl_errors (project_id);
CREATE INDEX idx_crawl_errors_error_code ON crawl_errors (error_code);
CREATE INDEX idx_crawl_errors_created_at ON crawl_errors (created_at);
CREATE INDEX idx_crawl_errors_job_id ON crawl_errors (job_id);
```

### Migrations

Schema changes are managed via Alembic migrations:

- **`add_crawler_integration_fields`**: Adds 10 fields to post_analytics, creates crawl_errors table
- **`24d42979e936_add_project_id_index`**: Adds performance index for project queries

---

## Configuration

### Required Environment Variables

```bash
# RabbitMQ Configuration (Input)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
EVENT_EXCHANGE=smap.events
EVENT_ROUTING_KEY=data.collected
EVENT_QUEUE_NAME=analytics.data.collected

# Result Publishing Configuration (Output)
PUBLISH_EXCHANGE=results.inbound
PUBLISH_ROUTING_KEY=analyze.result
PUBLISH_ENABLED=true

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_CRAWL_RESULTS_BUCKET=crawl-results
MINIO_USE_SSL=false

# PostgreSQL Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/analytics

# Batch Processing Configuration
MAX_CONCURRENT_BATCHES=5
BATCH_TIMEOUT_SECONDS=30

# Prometheus Metrics
PROMETHEUS_PORT=9090
```

### Performance Tuning

- **MAX_CONCURRENT_BATCHES**: Number of batches processed simultaneously (default: 5)
- **BATCH_TIMEOUT_SECONDS**: Timeout for batch processing (default: 30s)
- **Database Connection Pool**: Recommended 10-20 connections for production

---

## Performance Characteristics

### Target Metrics

| Metric                      | Target         | Notes                                  |
| --------------------------- | -------------- | -------------------------------------- |
| Batch processing p50        | < 2 seconds    | Median processing time per batch       |
| Batch processing p95        | < 5 seconds    | 95th percentile processing time        |
| Throughput (TikTok)         | 1000 items/min | 50 items/batch × 20 batches/min        |
| Throughput (YouTube)        | 300 items/min  | 20 items/batch × 15 batches/min        |
| Success rate                | > 95%          | Successful analytics pipeline runs     |
| Infrastructure error rate   | < 5%           | Database/MinIO/RabbitMQ failures       |
| Database write p95          | < 500ms        | Bulk insert latency                    |
| MinIO download p95          | < 1 second     | Batch download latency                 |
| End-to-end latency (median) | 1-2 minutes    | From crawler upload to analytics saved |

### Monitoring

Key metrics exposed via Prometheus (`http://localhost:9090/metrics`):

- `analytics_batch_processing_total{platform, status}` - Total batches processed
- `analytics_batch_processing_duration_seconds{platform}` - Processing time histogram
- `analytics_batch_size_mismatch_total{platform, expected_size, actual_size}` - Size mismatches
- `analytics_items_processed_total{platform, status}` - Total items processed
- `analytics_processing_errors_total{platform, error_category}` - Error distribution
- `analytics_active_batches` - Current batches being processed

---

## Migration Status

**Status**: ✅ Migration Complete (2025-12-07)

The Analytics Service has been fully migrated to the event-driven architecture:

### Completed Changes

- ✅ **Event Format**: Migrated to `data.collected` event schema
- ✅ **Feature Flags**: Removed `new_mode_enabled` and `legacy_mode_enabled`
- ✅ **Queue Configuration**: Direct binding to `smap.events` exchange
- ✅ **Batch Processing**: Default and only processing mode
- ✅ **Database Schema**: Extended with crawler integration fields
- ✅ **Error Handling**: Comprehensive error categorization
- ✅ **Monitoring**: Prometheus metrics for observability
- ✅ **Documentation**: Batch processing rationale documented

### Removed Components

- ❌ Legacy message format support
- ❌ Feature flag validation logic
- ❌ Direct queue consumption (now uses exchange binding)
- ❌ API service (replaced by event-driven flow)

### Historical Reference

For legacy configuration reference, see:

- `config/archive/legacy_queue_config.yaml`
- `openspec/changes/archive/2025-11-30-remove-api-service/`
- `openspec/changes/archive/2025-11-29-integrate-crawler-events/`

---

## Related Documentation

- [Event-Driven Architecture Guide](event-drivent.md) - Overall system architecture
- [Batch Processing Rationale](batch-processing-rationale.md) - Technical justification for batching
- [Integration Contract](integration-contract.md) - Crawler-Analytics interface specification
- [Integration Analytics Service](integration-analytics-service.md) - Analytics ↔ Collector integration guide
- [Analytics Orchestrator](analytic_orchestrator.md) - Analytics pipeline design
