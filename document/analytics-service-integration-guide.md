# ANALYTICS SERVICE INTEGRATION GUIDE

**Document Version:** 1.0
**Last Updated:** 2025-12-06
**Target Audience:** Analytics Service Development Team
**Status:** ✅ Crawler Implementation Complete - Ready for Analytics Integration

---

## Executive Summary

This document provides complete integration specifications for Analytics Service to consume crawler data via the new event-driven architecture. The Crawler service (TikTok & YouTube) has completed a major refactor implementing batch uploads to MinIO with `data.collected` events.

**Key Changes:**

1. ✅ Crawlers publish `data.collected` events to `smap.events` exchange
2. ✅ Data uploaded in batches to MinIO `crawl-results` bucket
3. ✅ Enhanced error reporting with 17 structured error codes
4. ✅ Project ID extraction from job IDs for cross-service tracking
5. ✅ Retry logic with exponential backoff for event publishing

**Analytics Service Action Required:**

- Implement consumer for `data.collected` events from `smap.events`
- Fetch batch data from MinIO using provided paths
- Process crawled content with enhanced error handling
- Update progress tracking and analytics dashboards

---

## Table of Contents

1. [Event Schema & Consumption](#1-event-schema--consumption)
2. [MinIO Batch Data Structure](#2-minio-batch-data-structure)
3. [Enhanced Error Reporting](#3-enhanced-error-reporting)
4. [Project ID Extraction](#4-project-id-extraction)
5. [Data Processing Workflow](#5-data-processing-workflow)
6. [Configuration Requirements](#6-configuration-requirements)
7. [Testing & Validation](#7-testing--validation)
8. [Performance Considerations](#8-performance-considerations)
9. [Monitoring & Observability](#9-monitoring--observability)
10. [Migration & Rollout](#10-migration--rollout)

---

## 1. Event Schema & Consumption

### 1.1. RabbitMQ Configuration

**Exchange:** `smap.events`
**Exchange Type:** `topic`
**Routing Key:** `data.collected`
**Queue Name:** `analytics.data.collected` (recommended)
**Queue Durability:** `true`
**Message Persistence:** Delivery mode 2 (persistent)

### 1.2. Event Schema

```json
{
  "event_id": "evt_abc123def456",
  "timestamp": "2025-12-06T10:30:00.000Z",
  "payload": {
    "project_id": "proj_xyz789",
    "job_id": "proj_xyz789-brand-0",
    "platform": "tiktok",
    "minio_path": "crawl-results/tiktok/proj_xyz789/brand/batch_000.json",
    "content_count": 50,
    "batch_index": 1,
    "total_batches": 10
  }
}
```

### 1.3. Field Specifications

| Field                   | Type    | Required | Description              | Example                      |
| ----------------------- | ------- | -------- | ------------------------ | ---------------------------- |
| `event_id`              | string  | Yes      | Unique event identifier  | `"evt_abc123def456"`         |
| `timestamp`             | string  | Yes      | ISO 8601 UTC timestamp   | `"2025-12-06T10:30:00.000Z"` |
| `payload.project_id`    | string  | Yes\*    | Project identifier       | `"proj_xyz789"` or `null`    |
| `payload.job_id`        | string  | Yes      | Job identifier           | `"proj_xyz789-brand-0"`      |
| `payload.platform`      | string  | Yes      | Platform name            | `"tiktok"` or `"youtube"`    |
| `payload.minio_path`    | string  | Yes      | Full MinIO path          | `"crawl-results/tiktok/..."` |
| `payload.content_count` | integer | Yes      | Items in batch           | `50`                         |
| `payload.batch_index`   | integer | Yes      | 1-based batch index      | `1`                          |
| `payload.total_batches` | integer | No       | Total batches (optional) | `10` or `null`               |

**Note:** `project_id` is `null` for dry-run tasks (UUID-based job_id)

### 1.4. Consumer Implementation (Python)

```python
import pika
import json
import logging

logger = logging.getLogger(__name__)

class DataCollectedConsumer:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None

    def connect(self):
        """Establish RabbitMQ connection."""
        self.connection = pika.BlockingConnection(
            pika.URLParameters(self.rabbitmq_url)
        )
        self.channel = self.connection.channel()

        # Declare exchange (idempotent)
        self.channel.exchange_declare(
            exchange='smap.events',
            exchange_type='topic',
            durable=True
        )

        # Declare queue
        self.channel.queue_declare(
            queue='analytics.data.collected',
            durable=True
        )

        # Bind queue to exchange
        self.channel.queue_bind(
            queue='analytics.data.collected',
            exchange='smap.events',
            routing_key='data.collected'
        )

        logger.info("Connected to RabbitMQ - Exchange: smap.events")

    def callback(self, ch, method, properties, body):
        """Process incoming data.collected event."""
        try:
            # Parse event
            event = json.loads(body)
            event_id = event['event_id']
            payload = event['payload']

            logger.info(
                f"Received data.collected event - ID: {event_id}, "
                f"Platform: {payload['platform']}, "
                f"Project: {payload.get('project_id', 'dry-run')}, "
                f"Batch: {payload['batch_index']}"
            )

            # Process batch
            self.process_batch(
                minio_path=payload['minio_path'],
                project_id=payload.get('project_id'),
                job_id=payload['job_id'],
                platform=payload['platform'],
                content_count=payload['content_count'],
                batch_index=payload['batch_index']
            )

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as exc:
            logger.error(f"Error processing event: {exc}", exc_info=True)
            # Negative acknowledge - requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def process_batch(self, minio_path, project_id, job_id, platform, content_count, batch_index):
        """Process a single batch - implement your logic here."""
        # See Section 5 for implementation details
        pass

    def start_consuming(self):
        """Start consuming messages."""
        self.channel.basic_qos(prefetch_count=1)  # Process one at a time
        self.channel.basic_consume(
            queue='analytics.data.collected',
            on_message_callback=self.callback,
            auto_ack=False  # Manual ack for reliability
        )

        logger.info("Started consuming data.collected events")
        self.channel.start_consuming()

    def close(self):
        """Close connection."""
        if self.channel:
            self.channel.close()
        if self.connection:
            self.connection.close()

# Usage
consumer = DataCollectedConsumer('amqp://user:pass@rabbitmq:5672/')
consumer.connect()
consumer.start_consuming()
```

---

## 2. MinIO Batch Data Structure

### 2.1. Bucket and Path Format

**Bucket:** `crawl-results`

**Path Pattern:**

```
crawl-results/{platform}/{project_id}/{subfolder}/batch_{index:03d}.json
```

**Path Examples:**

```
# Brand keywords (TikTok)
crawl-results/tiktok/proj_xyz789/brand/batch_000.json
crawl-results/tiktok/proj_xyz789/brand/batch_001.json
crawl-results/tiktok/proj_xyz789/brand/batch_002.json

# Competitor keywords (TikTok)
crawl-results/tiktok/proj_xyz789/competitor_toyota/batch_000.json
crawl-results/tiktok/proj_xyz789/competitor_honda/batch_000.json

# Brand keywords (YouTube)
crawl-results/youtube/proj_abc123/brand/batch_000.json

# Dry-run (no project_id)
crawl-results/tiktok/dryrun/550e8400-e29b-41d4-a716-446655440000/batch_000.json
```

### 2.2. Batch Sizes by Platform

| Platform    | Batch Size | Reason                                                  |
| ----------- | ---------- | ------------------------------------------------------- |
| **TikTok**  | 50 items   | Smaller content objects (~5-10KB per item)              |
| **YouTube** | 20 items   | Larger content with transcriptions (~50-100KB per item) |

### 2.3. Batch File Structure

Each batch file contains a JSON array of crawled items:

```json
[
  {
    "meta": {
      /* Metadata about the crawl */
    },
    "content": {
      /* Content data */
    },
    "author": {
      /* Author/Channel data */
    },
    "comments": [
      /* Array of comments */
    ]
  },
  {
    "meta": {
      /* ... */
    },
    "content": {
      /* ... */
    },
    "author": {
      /* ... */
    },
    "comments": [
      /* ... */
    ]
  }
  // ... up to 50 items (TikTok) or 20 items (YouTube)
]
```

### 2.4. Complete Item Schema (TikTok Example)

```json
{
  "meta": {
    "id": "video7312345678901234567",
    "platform": "tiktok",
    "job_id": "proj_xyz789-brand-0",
    "task_type": "research_and_crawl",
    "crawled_at": "2025-12-06T10:15:30.123Z",
    "published_at": "2025-12-05T15:30:00.000Z",
    "permalink": "https://www.tiktok.com/@username/video/7312345678901234567",
    "keyword_source": "VinFast VF8",
    "lang": "vi",
    "region": "VN",
    "pipeline_version": "crawler_tiktok_v3",
    "fetch_status": "success",
    "fetch_error": null,
    "error_code": null,
    "error_details": {}
  },
  "content": {
    "external_id": "7312345678901234567",
    "url": "https://www.tiktok.com/@username/video/7312345678901234567",
    "description": "Amazing VinFast VF8 electric SUV review! Best EV in Vietnam 🚗⚡ #VinFast #VF8 #ElectricVehicle #EVReview",
    "view_count": 125340,
    "like_count": 8567,
    "comment_count": 342,
    "share_count": 156,
    "save_count": 89,
    "duration_seconds": 45,
    "tags": ["VinFast", "VF8", "ElectricVehicle", "EVReview", "Vietnam"],
    "sound_name": "Original Sound - username",
    "category": "Automotive",
    "media_type": "audio",
    "media_path": "tiktok/audio/proj_xyz789/7312345678901234567.mp3",
    "transcription": "Hôm nay mình sẽ review VinFast VF8, chiếc xe điện được nhiều người quan tâm nhất Việt Nam...",
    "transcription_status": "completed",
    "transcription_error": null
  },
  "author": {
    "username": "carevolutionvn",
    "display_name": "Car Evolution VN",
    "avatar_url": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/abc123~c5_1080x1080.jpeg",
    "bio": "Automotive Reviewer 🚗 | EV Enthusiast ⚡ | Vietnam",
    "follower_count": 125000,
    "following_count": 456,
    "total_likes": 2567890,
    "video_count": 342,
    "verified": true
  },
  "comments": [
    {
      "external_id": "7312345678901234999",
      "author_username": "nguyenvana",
      "author_display_name": "Nguyen Van A",
      "text": "Xe đẹp quá! Muốn mua VF8 lắm rồi!",
      "like_count": 45,
      "reply_count": 3,
      "created_at": "2025-12-05T16:00:00.000Z",
      "parent_type": "CONTENT"
    },
    {
      "external_id": "7312345678901235000",
      "author_username": "tranthib",
      "author_display_name": "Tran Thi B",
      "text": "Giá bao nhiêu vậy bạn?",
      "like_count": 12,
      "reply_count": 1,
      "created_at": "2025-12-05T16:15:00.000Z",
      "parent_type": "CONTENT"
    }
  ]
}
```

### 2.5. YouTube Item Schema Differences

YouTube items have additional fields:

```json
{
  "content": {
    "channel_id": "UCxyz123",
    "video_id": "dQw4w9WgXcQ",
    "category_id": "2", // YouTube category
    "definition": "hd", // "hd" or "sd"
    "caption": "true" // Has captions
    // ... other fields similar to TikTok
  }
}
```

### 2.6. Fetching Batch Data from MinIO

**Python with boto3:**

```python
import boto3
import json
import zstandard as zstd

class MinIOBatchFetcher:
    def __init__(self, endpoint, access_key, secret_key, use_ssl=False):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"{'https' if use_ssl else 'http'}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

    def fetch_batch(self, minio_path: str) -> list:
        """
        Fetch and parse batch file from MinIO.

        Args:
            minio_path: Full path (e.g., "crawl-results/tiktok/proj_xyz/brand/batch_000.json")

        Returns:
            List of crawled items

        Raises:
            Exception: If fetch or parsing fails
        """
        # Parse bucket and key from path
        parts = minio_path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''

        # Fetch object from MinIO
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        body = response['Body'].read()

        # Handle compression if enabled (check file extension)
        if key.endswith('.zst'):
            # Decompress using Zstandard
            dctx = zstd.ZstdDecompressor()
            body = dctx.decompress(body)

        # Parse JSON
        items = json.loads(body)

        return items

# Usage
fetcher = MinIOBatchFetcher(
    endpoint='minio:9000',
    access_key='your_access_key',
    secret_key='your_secret_key',
    use_ssl=False
)

items = fetcher.fetch_batch('crawl-results/tiktok/proj_xyz/brand/batch_000.json')
print(f"Fetched {len(items)} items")
```

---

## 3. Enhanced Error Reporting

### 3.1. Error Code Taxonomy

Crawlers now return structured error codes categorized by type:

| Category          | Error Codes                                                | Count |
| ----------------- | ---------------------------------------------------------- | ----- |
| **Rate Limiting** | RATE_LIMITED, AUTH_FAILED, ACCESS_DENIED                   | 3     |
| **Content**       | CONTENT_REMOVED, CONTENT_NOT_FOUND, CONTENT_UNAVAILABLE    | 3     |
| **Network**       | NETWORK_ERROR, TIMEOUT, CONNECTION_REFUSED, DNS_ERROR      | 4     |
| **Parsing**       | PARSE_ERROR, INVALID_URL, INVALID_RESPONSE                 | 3     |
| **Media**         | MEDIA_DOWNLOAD_FAILED, MEDIA_TOO_LARGE, MEDIA_FORMAT_ERROR | 3     |
| **Storage**       | STORAGE_ERROR, UPLOAD_FAILED                               | 2     |
| **Generic**       | UNKNOWN_ERROR, INTERNAL_ERROR, DATABASE_ERROR              | 3     |

### 3.2. Error Code Reference

| Error Code              | Description                                  | Recommended Action                      | Retry? |
| ----------------------- | -------------------------------------------- | --------------------------------------- | ------ |
| `RATE_LIMITED`          | Platform rate limiting                       | Wait and retry with exponential backoff | Yes    |
| `AUTH_FAILED`           | Authentication/authorization failed          | Alert team, check credentials           | No     |
| `ACCESS_DENIED`         | Content access denied (private, geo-blocked) | Skip, mark as inaccessible              | No     |
| `CONTENT_REMOVED`       | Content was deleted by author                | Skip permanently, mark as removed       | No     |
| `CONTENT_NOT_FOUND`     | Content doesn't exist (404)                  | Skip permanently, mark as not found     | No     |
| `CONTENT_UNAVAILABLE`   | Content temporarily unavailable              | Retry later                             | Yes    |
| `NETWORK_ERROR`         | General network connectivity issue           | Retry with exponential backoff          | Yes    |
| `TIMEOUT`               | Request timed out                            | Retry with increased timeout            | Yes    |
| `CONNECTION_REFUSED`    | Server refused connection                    | Alert team, check service health        | No     |
| `DNS_ERROR`             | DNS resolution failed                        | Alert team, check network               | No     |
| `PARSE_ERROR`           | Failed to parse response data                | Alert team for investigation            | No     |
| `INVALID_URL`           | URL format is invalid                        | Skip permanently, log for review        | No     |
| `INVALID_RESPONSE`      | Response format unexpected                   | Alert team, may need crawler update     | No     |
| `MEDIA_DOWNLOAD_FAILED` | Failed to download media file                | Use metadata only, skip media           | No     |
| `MEDIA_TOO_LARGE`       | Media file exceeds size limit                | Use metadata only, skip media           | No     |
| `MEDIA_FORMAT_ERROR`    | Unsupported media format                     | Use metadata only, skip media           | No     |
| `STORAGE_ERROR`         | MinIO/storage operation failed               | Retry, alert if persistent              | Yes    |
| `UPLOAD_FAILED`         | Failed to upload to storage                  | Retry, alert if persistent              | Yes    |
| `DATABASE_ERROR`        | MongoDB operation failed                     | Retry, alert team                       | Yes    |
| `UNKNOWN_ERROR`         | Unclassified error                           | Alert team for investigation            | Maybe  |
| `INTERNAL_ERROR`        | Internal service error                       | Alert team, check crawler logs          | Yes    |

### 3.3. Error Item Schema

When crawling fails, the item will have `fetch_status = "error"`:

```json
{
  "meta": {
    "id": "video7312345678901234568",
    "platform": "tiktok",
    "job_id": "proj_xyz789-brand-0",
    "task_type": "research_and_crawl",
    "crawled_at": "2025-12-06T10:15:30.123Z",
    "permalink": "https://www.tiktok.com/@username/video/7312345678901234568",
    "keyword_source": "VinFast VF8",
    "fetch_status": "error",
    "fetch_error": "Content has been removed by the author",
    "error_code": "CONTENT_REMOVED",
    "error_details": {
      "exception_type": "ContentRemovedError",
      "url": "https://www.tiktok.com/@username/video/7312345678901234568",
      "response_code": 404
    }
  },
  "content": null,
  "author": null,
  "comments": []
}
```

### 3.4. Error Handling Strategy

```python
def process_item(item: dict) -> dict:
    """
    Process a single item with error handling.

    Returns:
        Processing result with status and metrics
    """
    meta = item['meta']
    fetch_status = meta.get('fetch_status', 'unknown')

    if fetch_status == 'success':
        # Process successful item
        return process_success_item(item)

    elif fetch_status == 'error':
        # Handle error item
        error_code = meta.get('error_code', 'UNKNOWN_ERROR')
        error_message = meta.get('fetch_error', 'Unknown error')

        # Categorize error
        category = categorize_error_code(error_code)

        # Log error
        logger.warning(
            f"Crawl error - ID: {meta['id']}, "
            f"Code: {error_code}, "
            f"Category: {category}, "
            f"Message: {error_message}"
        )

        # Store error record
        store_error_record(
            content_id=meta['id'],
            job_id=meta['job_id'],
            platform=meta['platform'],
            error_code=error_code,
            error_message=error_message,
            error_details=meta.get('error_details', {}),
            permalink=meta.get('permalink')
        )

        return {
            'status': 'error',
            'error_code': error_code,
            'category': category
        }

    else:
        logger.error(f"Unknown fetch_status: {fetch_status}")
        return {'status': 'unknown'}

def categorize_error_code(error_code: str) -> str:
    """Categorize error code for reporting."""
    error_categories = {
        'rate_limiting': ['RATE_LIMITED', 'AUTH_FAILED', 'ACCESS_DENIED'],
        'content': ['CONTENT_REMOVED', 'CONTENT_NOT_FOUND', 'CONTENT_UNAVAILABLE'],
        'network': ['NETWORK_ERROR', 'TIMEOUT', 'CONNECTION_REFUSED', 'DNS_ERROR'],
        'parsing': ['PARSE_ERROR', 'INVALID_URL', 'INVALID_RESPONSE'],
        'media': ['MEDIA_DOWNLOAD_FAILED', 'MEDIA_TOO_LARGE', 'MEDIA_FORMAT_ERROR'],
        'storage': ['STORAGE_ERROR', 'UPLOAD_FAILED', 'DATABASE_ERROR'],
        'generic': ['UNKNOWN_ERROR', 'INTERNAL_ERROR']
    }

    for category, codes in error_categories.items():
        if error_code in codes:
            return category

    return 'unknown'
```

---

## 4. Project ID Extraction

### 4.1. Job ID Format Patterns

| Task Type               | Job ID Pattern                     | Project ID    | Example                                         |
| ----------------------- | ---------------------------------- | ------------- | ----------------------------------------------- |
| **Brand Keywords**      | `{projectID}-brand-{index}`        | `{projectID}` | `proj_xyz789-brand-0` → `proj_xyz789`           |
| **Competitor Keywords** | `{projectID}-{competitor}-{index}` | `{projectID}` | `proj_xyz789-toyota-5` → `proj_xyz789`          |
| **Dry-Run**             | `{uuid}`                           | `null`        | `550e8400-e29b-41d4-a716-446655440000` → `null` |

### 4.2. Extraction Implementation

```python
import re
from typing import Optional

def extract_project_id(job_id: str) -> Optional[str]:
    """
    Extract project_id from job_id.

    Supports formats:
    - Brand: {projectID}-brand-{index}
    - Competitor: {projectID}-{competitor}-{index}
    - Dry-run: {uuid} (returns None)

    Args:
        job_id: Job identifier string

    Returns:
        project_id if found, None for dry-run (UUID) or invalid format

    Examples:
        >>> extract_project_id("proj_xyz789-brand-0")
        'proj_xyz789'
        >>> extract_project_id("proj_abc123-toyota-5")
        'proj_abc123'
        >>> extract_project_id("550e8400-e29b-41d4-a716-446655440000")
        None
    """
    if not job_id:
        return None

    # Check if UUID format (dry-run)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, job_id, re.IGNORECASE):
        return None

    # Split by '-'
    parts = job_id.split('-')
    if len(parts) < 3:
        return None

    # Last part should be numeric index
    if not parts[-1].isdigit():
        return None

    # Everything except last 2 parts is project_id
    # Examples:
    #   proj_xyz789-brand-0 → proj_xyz789
    #   proj-with-hyphens-toyota-5 → proj-with-hyphens
    project_id = '-'.join(parts[:-2])
    return project_id if project_id else None

# Unit tests
def test_extract_project_id():
    # Brand format
    assert extract_project_id("proj_xyz789-brand-0") == "proj_xyz789"
    assert extract_project_id("my_project-brand-10") == "my_project"

    # Competitor format
    assert extract_project_id("proj_xyz789-toyota-5") == "proj_xyz789"
    assert extract_project_id("proj_abc-honda-0") == "proj_abc"

    # Complex project IDs
    assert extract_project_id("my-complex-project-brand-0") == "my-complex-project"
    assert extract_project_id("proj-with-many-parts-competitor-5") == "proj-with-many-parts"

    # Dry-run (UUID)
    assert extract_project_id("550e8400-e29b-41d4-a716-446655440000") is None
    assert extract_project_id("123e4567-e89b-12d3-a456-426614174000") is None

    # Invalid formats
    assert extract_project_id("") is None
    assert extract_project_id("single") is None
    assert extract_project_id("proj-brand") is None
    assert extract_project_id("proj-brand-abc") is None

    print("✓ All tests passed")

test_extract_project_id()
```

### 4.3. Usage in Analytics

```python
def process_batch(items: list, job_id: str):
    """Process batch with project_id extraction."""

    # Extract project_id from job_id
    project_id = extract_project_id(job_id)

    # Determine if this is a dry-run or project execution
    is_dryrun = project_id is None

    for item in items:
        meta = item['meta']

        # Add extracted project_id to item
        item['project_id'] = project_id
        item['is_dryrun'] = is_dryrun

        # Process based on type
        if is_dryrun:
            process_dryrun_item(item)
        else:
            process_project_item(item, project_id)
```

---

## 5. Data Processing Workflow

### 5.1. End-to-End Processing Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Receive data.collected Event from RabbitMQ              │
│    - Exchange: smap.events                                  │
│    - Routing Key: data.collected                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Parse Event & Extract Metadata                          │
│    - event_id, timestamp                                    │
│    - project_id, job_id, platform                          │
│    - minio_path, content_count, batch_index                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Fetch Batch File from MinIO                             │
│    - Connect to MinIO                                       │
│    - GET object from crawl-results bucket                   │
│    - Decompress if .zst extension                           │
│    - Parse JSON array                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Extract Project ID                                       │
│    - Call extract_project_id(job_id)                       │
│    - Determine if dry-run (project_id == null)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Process Each Item in Batch                              │
│    For each item:                                           │
│    ├─ Check fetch_status                                    │
│    ├─ If "success": Process content, author, comments       │
│    ├─ If "error": Log error, categorize, store error record │
│    └─ Update counters (success_count, error_count)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Store Processed Data                                     │
│    - Insert content records into database                   │
│    - Insert author records                                  │
│    - Insert comment records                                 │
│    - Link to project_id                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Update Analytics Metrics                                 │
│    - Increment processed item counter                       │
│    - Update error rate metrics                              │
│    - Calculate error distribution                           │
│    - Update project progress                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Acknowledge RabbitMQ Message                             │
│    - ch.basic_ack() for success                             │
│    - ch.basic_nack() for failure (requeue)                  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2. Complete Implementation Example

```python
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, minio_fetcher, database, metrics_tracker):
        self.minio_fetcher = minio_fetcher
        self.database = database
        self.metrics = metrics_tracker

    def process_event(self, event: Dict) -> Dict:
        """
        Process a data.collected event end-to-end.

        Args:
            event: Parsed event from RabbitMQ

        Returns:
            Processing result with metrics
        """
        start_time = datetime.utcnow()
        event_id = event['event_id']
        payload = event['payload']

        logger.info(
            f"Processing event {event_id} - "
            f"Platform: {payload['platform']}, "
            f"Project: {payload.get('project_id', 'dry-run')}, "
            f"Batch: {payload['batch_index']}/{payload.get('total_batches', '?')}"
        )

        try:
            # Step 1: Fetch batch from MinIO
            items = self.minio_fetcher.fetch_batch(payload['minio_path'])
            logger.info(f"Fetched {len(items)} items from MinIO")

            # Step 2: Extract project ID
            project_id = extract_project_id(payload['job_id'])
            is_dryrun = project_id is None

            # Step 3: Process items
            results = []
            for item in items:
                result = self.process_item(item, project_id, is_dryrun)
                results.append(result)

            # Step 4: Aggregate metrics
            success_count = sum(1 for r in results if r['status'] == 'success')
            error_count = sum(1 for r in results if r['status'] == 'error')

            error_distribution = {}
            for r in results:
                if r['status'] == 'error':
                    code = r.get('error_code', 'UNKNOWN')
                    error_distribution[code] = error_distribution.get(code, 0) + 1

            # Step 5: Update analytics metrics
            self.metrics.update(
                project_id=project_id,
                platform=payload['platform'],
                batch_index=payload['batch_index'],
                success_count=success_count,
                error_count=error_count,
                error_distribution=error_distribution
            )

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Completed event {event_id} - "
                f"Success: {success_count}, Errors: {error_count}, "
                f"Time: {processing_time:.2f}s"
            )

            return {
                'status': 'completed',
                'event_id': event_id,
                'items_processed': len(items),
                'success_count': success_count,
                'error_count': error_count,
                'error_distribution': error_distribution,
                'processing_time_seconds': processing_time
            }

        except Exception as exc:
            logger.error(f"Error processing event {event_id}: {exc}", exc_info=True)
            return {
                'status': 'failed',
                'event_id': event_id,
                'error': str(exc)
            }

    def process_item(self, item: Dict, project_id: Optional[str], is_dryrun: bool) -> Dict:
        """Process a single item."""
        meta = item['meta']
        content_id = meta['id']
        fetch_status = meta.get('fetch_status', 'unknown')

        if fetch_status == 'success':
            # Store content, author, comments
            self.database.insert_content(
                content=item['content'],
                author=item['author'],
                comments=item['comments'],
                meta=meta,
                project_id=project_id,
                is_dryrun=is_dryrun
            )

            return {
                'status': 'success',
                'content_id': content_id
            }

        elif fetch_status == 'error':
            error_code = meta.get('error_code', 'UNKNOWN_ERROR')
            error_message = meta.get('fetch_error', 'Unknown error')

            # Store error record
            self.database.insert_error_record(
                content_id=content_id,
                job_id=meta['job_id'],
                platform=meta['platform'],
                error_code=error_code,
                error_message=error_message,
                error_details=meta.get('error_details', {}),
                permalink=meta.get('permalink'),
                project_id=project_id
            )

            return {
                'status': 'error',
                'content_id': content_id,
                'error_code': error_code,
                'category': categorize_error_code(error_code)
            }

        else:
            logger.warning(f"Unknown fetch_status: {fetch_status} for item {content_id}")
            return {
                'status': 'unknown',
                'content_id': content_id
            }
```

---

## 6. Configuration Requirements

### 6.1. Environment Variables

```env
# ========== RabbitMQ Configuration ==========
RABBITMQ_HOST=rabbitmq-host
RABBITMQ_PORT=5672
RABBITMQ_USER=analytics_user
RABBITMQ_PASSWORD=analytics_secure_password
RABBITMQ_VHOST=/

# Event consumption
EVENT_EXCHANGE=smap.events
EVENT_QUEUE=analytics.data.collected
EVENT_ROUTING_KEY=data.collected
EVENT_PREFETCH_COUNT=1  # Process one batch at a time

# ========== MinIO Configuration ==========
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=analytics_minio_key
MINIO_SECRET_KEY=analytics_minio_secret
MINIO_USE_SSL=false
MINIO_CRAWL_RESULTS_BUCKET=crawl-results

# Connection pooling
MINIO_MAX_POOL_CONNECTIONS=10

# ========== Database Configuration ==========
DATABASE_URL=postgresql://analytics:password@postgres:5432/analytics
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ========== Processing Configuration ==========
# Concurrency
MAX_CONCURRENT_BATCH_PROCESSING=5
MAX_WORKERS=10

# Retry settings
MAX_RETRY_ATTEMPTS=3
RETRY_INITIAL_DELAY=1.0  # seconds
RETRY_MAX_DELAY=30.0
RETRY_BACKOFF_MULTIPLIER=2.0

# ========== Error Handling ==========
# Alert thresholds
ERROR_ALERT_THRESHOLD=10  # Alert when error rate > 10%
ERROR_SPIKE_THRESHOLD=5   # Alert when errors increase by 5x

# Permanent errors (don't retry)
PERMANENT_ERROR_CODES=CONTENT_REMOVED,CONTENT_NOT_FOUND,INVALID_URL,ACCESS_DENIED

# Transient errors (retry with backoff)
TRANSIENT_ERROR_CODES=NETWORK_ERROR,TIMEOUT,RATE_LIMITED,CONTENT_UNAVAILABLE,STORAGE_ERROR

# ========== Monitoring ==========
METRICS_ENABLED=true
METRICS_PORT=9090
LOG_LEVEL=INFO
```

### 6.2. Configuration Class (Python)

```python
from pydantic_settings import BaseSettings
from typing import List

class AnalyticsConfig(BaseSettings):
    """Analytics Service Configuration"""

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "analytics"
    rabbitmq_password: str
    rabbitmq_vhost: str = "/"

    event_exchange: str = "smap.events"
    event_queue: str = "analytics.data.collected"
    event_routing_key: str = "data.collected"
    event_prefetch_count: int = 1

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_use_ssl: bool = False
    minio_crawl_results_bucket: str = "crawl-results"
    minio_max_pool_connections: int = 10

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Processing
    max_concurrent_batch_processing: int = 5
    max_workers: int = 10

    # Retry
    max_retry_attempts: int = 3
    retry_initial_delay: float = 1.0
    retry_max_delay: float = 30.0
    retry_backoff_multiplier: float = 2.0

    # Error handling
    error_alert_threshold: float = 10.0
    error_spike_threshold: int = 5
    permanent_error_codes: List[str] = [
        "CONTENT_REMOVED",
        "CONTENT_NOT_FOUND",
        "INVALID_URL",
        "ACCESS_DENIED"
    ]
    transient_error_codes: List[str] = [
        "NETWORK_ERROR",
        "TIMEOUT",
        "RATE_LIMITED",
        "CONTENT_UNAVAILABLE",
        "STORAGE_ERROR"
    ]

    # Monitoring
    metrics_enabled: bool = True
    metrics_port: int = 9090
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

# Usage
config = AnalyticsConfig()
```

---

## 7. Testing & Validation

### 7.1. Integration Test Checklist

**RabbitMQ Integration:**

- [ ] Can connect to RabbitMQ exchange `smap.events`
- [ ] Can declare and bind queue `analytics.data.collected`
- [ ] Can consume messages with routing key `data.collected`
- [ ] Can parse event JSON schema correctly
- [ ] Can handle message acknowledgments (ack/nack)
- [ ] Can recover from connection failures

**MinIO Integration:**

- [ ] Can connect to MinIO endpoint
- [ ] Can fetch batch files from `crawl-results` bucket
- [ ] Can handle compressed files (.zst extension)
- [ ] Can parse batch JSON arrays
- [ ] Can handle MinIO fetch errors gracefully
- [ ] Connection pooling works correctly

**Data Processing:**

- [ ] Can extract project_id from all job_id formats
- [ ] Correctly identifies dry-run tasks (UUID job_id)
- [ ] Can process success items (fetch_status = "success")
- [ ] Can process error items (fetch_status = "error")
- [ ] Can categorize errors by error_code
- [ ] Can calculate error distribution
- [ ] Can store processed data in database

**Error Handling:**

- [ ] Retries transient errors with exponential backoff
- [ ] Skips permanent errors without retry
- [ ] Logs all errors with context
- [ ] Alerts on error rate threshold exceeded
- [ ] Handles malformed events gracefully

**Metrics & Monitoring:**

- [ ] Tracks events received count
- [ ] Tracks batches processed count
- [ ] Tracks items processed count
- [ ] Calculates success/error rates
- [ ] Measures processing latency
- [ ] Exposes metrics endpoint

### 7.2. Sample Test Data

**Mock data.collected Event:**

```json
{
  "event_id": "evt_test123abc",
  "timestamp": "2025-12-06T10:00:00.000Z",
  "payload": {
    "project_id": "proj_test_xyz",
    "job_id": "proj_test_xyz-brand-0",
    "platform": "tiktok",
    "minio_path": "crawl-results/tiktok/proj_test_xyz/brand/batch_000.json",
    "content_count": 50,
    "batch_index": 1,
    "total_batches": 5
  }
}
```

**Mock Batch File (2 items - 1 success, 1 error):**

```json
[
  {
    "meta": {
      "id": "video_success_001",
      "platform": "tiktok",
      "job_id": "proj_test_xyz-brand-0",
      "task_type": "research_and_crawl",
      "fetch_status": "success",
      "fetch_error": null,
      "error_code": null
    },
    "content": {
      "external_id": "video_success_001",
      "url": "https://tiktok.com/@test/video/001",
      "description": "Test video",
      "view_count": 1000
    },
    "author": {
      "username": "testuser",
      "display_name": "Test User"
    },
    "comments": []
  },
  {
    "meta": {
      "id": "video_error_002",
      "platform": "tiktok",
      "job_id": "proj_test_xyz-brand-0",
      "task_type": "research_and_crawl",
      "fetch_status": "error",
      "fetch_error": "Content has been removed",
      "error_code": "CONTENT_REMOVED",
      "error_details": {
        "exception_type": "ContentRemovedError"
      }
    },
    "content": null,
    "author": null,
    "comments": []
  }
]
```

### 7.3. Test Scenarios

**Test 1: Happy Path**

- Receive event → Fetch batch → Process all success items → Store in DB → Ack message
- Expected: 100% success rate, 0 errors

**Test 2: Error Handling**

- Receive event → Fetch batch → Process mixed success/error items → Store both → Ack message
- Expected: Correct error categorization, error metrics updated

**Test 3: MinIO Fetch Failure**

- Receive event → MinIO fetch fails → Nack message (requeue)
- Expected: Message requeued for retry

**Test 4: Dry-Run Processing**

- Receive event with UUID job_id → Extract project_id (null) → Process as dry-run
- Expected: Items not linked to project, marked as dry-run

**Test 5: Compressed Batch**

- Receive event → Fetch .zst compressed batch → Decompress → Parse → Process
- Expected: Correct decompression and processing

---

## 8. Performance Considerations

### 8.1. Batch Processing Performance

| Metric                 | Target          | Notes             |
| ---------------------- | --------------- | ----------------- |
| Batch Fetch Latency    | < 500ms         | From MinIO        |
| Batch Parse Time       | < 100ms         | JSON parsing      |
| Item Processing Time   | < 50ms per item | Database insert   |
| Total Batch Processing | < 5s            | For 50-item batch |
| Concurrent Batches     | 5 batches       | Recommended max   |

### 8.2. Throughput Estimates

**TikTok:**

- Batch size: 50 items
- Processing time: ~3s per batch
- Throughput: ~1000 items/minute (with 5 concurrent workers)

**YouTube:**

- Batch size: 20 items (larger content)
- Processing time: ~4s per batch
- Throughput: ~300 items/minute (with 5 concurrent workers)

**Daily Volume:**

- Expected: 10-20 projects/day
- Items per project: 1000-5000
- Total daily items: 50,000-100,000
- Processing time: 1-2 hours

### 8.3. Optimization Strategies

**1. Connection Pooling:**

```python
# MinIO connection pool
s3_client = boto3.client(
    's3',
    endpoint_url=minio_endpoint,
    config=Config(
        max_pool_connections=10,
        retries={'max_attempts': 3}
    )
)

# Database connection pool
engine = create_engine(
    database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

**2. Batch Database Inserts:**

```python
# Insert multiple items in single transaction
def bulk_insert_items(items: List[Dict]):
    with database.begin() as conn:
        # Bulk insert content
        conn.execute(
            content_table.insert(),
            [item['content'] for item in items]
        )
        # Bulk insert authors
        conn.execute(
            author_table.insert(),
            [item['author'] for item in items]
        )
```

**3. Async Processing:**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_batches_async(events: List[Dict]):
    """Process multiple batches concurrently."""
    with ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, process_batch, event)
            for event in events
        ]
        results = await asyncio.gather(*tasks)
    return results
```

**4. Caching:**

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_author_id(username: str) -> Optional[int]:
    """Cache author lookups to avoid duplicate DB queries."""
    return database.query_author_id(username)
```

### 8.4. Resource Requirements

**Minimum Requirements:**

- CPU: 2 cores
- RAM: 4GB
- Network: 100 Mbps

**Recommended (Production):**

- CPU: 4-8 cores
- RAM: 8-16GB
- Network: 1 Gbps
- Storage: SSD for database

---

## 9. Monitoring & Observability

### 9.1. Key Metrics

**Event Consumption Metrics:**
| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|----------------|
| `events_received_total` | Counter | Total events received | N/A |
| `events_processed_total` | Counter | Successfully processed events | N/A |
| `events_failed_total` | Counter | Failed event processing | > 10/hour |
| `event_processing_duration_seconds` | Histogram | Event processing latency | p95 > 10s |

**Batch Processing Metrics:**
| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|----------------|
| `batches_fetched_total` | Counter | Batches fetched from MinIO | N/A |
| `batches_processed_total` | Counter | Successfully processed batches | N/A |
| `batch_fetch_duration_seconds` | Histogram | MinIO fetch latency | p95 > 1s |
| `batch_parse_duration_seconds` | Histogram | JSON parse latency | p95 > 500ms |

**Item Processing Metrics:**
| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|----------------|
| `items_processed_total` | Counter | Total items processed | N/A |
| `items_success_total` | Counter | Success items | N/A |
| `items_error_total` | Counter | Error items | Rate > 10% |
| `success_rate` | Gauge | Success rate percentage | < 90% |
| `error_rate` | Gauge | Error rate percentage | > 10% |

**Error Distribution Metrics:**
| Metric | Type | Description |
|--------|------|-------------|
| `errors_by_code_total` | Counter (labeled by error_code) | Error count by code |
| `errors_by_category_total` | Counter (labeled by category) | Error count by category |
| `errors_by_platform_total` | Counter (labeled by platform) | Error count by platform |

**Infrastructure Metrics:**
| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|----------------|
| `rabbitmq_connection_status` | Gauge | RabbitMQ connection (0/1) | == 0 |
| `minio_connection_errors_total` | Counter | MinIO connection errors | > 10/hour |
| `database_connection_pool_size` | Gauge | Active DB connections | > 80% pool size |

### 9.2. Prometheus Metrics Example

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Event metrics
events_received = Counter(
    'analytics_events_received_total',
    'Total data.collected events received'
)
events_processed = Counter(
    'analytics_events_processed_total',
    'Successfully processed events',
    ['platform']
)
event_duration = Histogram(
    'analytics_event_processing_duration_seconds',
    'Event processing duration',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# Item metrics
items_processed = Counter(
    'analytics_items_processed_total',
    'Total items processed',
    ['platform', 'status']  # status: success/error
)
success_rate = Gauge(
    'analytics_success_rate',
    'Success rate percentage',
    ['platform']
)
error_rate = Gauge(
    'analytics_error_rate',
    'Error rate percentage',
    ['platform']
)

# Error distribution
errors_by_code = Counter(
    'analytics_errors_by_code_total',
    'Errors by error code',
    ['error_code', 'platform']
)

# Usage in processing
def process_batch_with_metrics(event):
    platform = event['payload']['platform']

    events_received.inc()

    with event_duration.time():
        result = process_batch(event)

    if result['status'] == 'completed':
        events_processed.labels(platform=platform).inc()

        # Update item metrics
        items_processed.labels(
            platform=platform,
            status='success'
        ).inc(result['success_count'])

        items_processed.labels(
            platform=platform,
            status='error'
        ).inc(result['error_count'])

        # Update error distribution
        for error_code, count in result['error_distribution'].items():
            errors_by_code.labels(
                error_code=error_code,
                platform=platform
            ).inc(count)

        # Update rates
        total = result['success_count'] + result['error_count']
        if total > 0:
            success_rate.labels(platform=platform).set(
                (result['success_count'] / total) * 100
            )
            error_rate.labels(platform=platform).set(
                (result['error_count'] / total) * 100
            )

# Start metrics server
start_http_server(9090)
```

### 9.3. Logging Strategy

**Log Levels:**

- **DEBUG:** Detailed processing info (item-level)
- **INFO:** Important events (batch start/complete, milestones)
- **WARNING:** Recoverable errors, retries
- **ERROR:** Processing failures, unhandled exceptions
- **CRITICAL:** Service failures, connection losses

**Structured Logging Example:**

```python
import logging
import json

logger = logging.getLogger(__name__)

def log_event_received(event_id, project_id, platform, batch_index):
    logger.info(
        "Event received",
        extra={
            'event_id': event_id,
            'project_id': project_id,
            'platform': platform,
            'batch_index': batch_index,
            'event_type': 'data.collected'
        }
    )

def log_batch_processed(event_id, success_count, error_count, duration):
    logger.info(
        "Batch processed",
        extra={
            'event_id': event_id,
            'success_count': success_count,
            'error_count': error_count,
            'processing_duration_seconds': duration,
            'success_rate': (success_count / (success_count + error_count)) * 100
        }
    )

def log_error_item(content_id, job_id, error_code, error_message):
    logger.warning(
        "Error item encountered",
        extra={
            'content_id': content_id,
            'job_id': job_id,
            'error_code': error_code,
            'error_message': error_message
        }
    )

def log_processing_failure(event_id, exception):
    logger.error(
        "Batch processing failed",
        extra={
            'event_id': event_id,
            'exception_type': type(exception).__name__,
            'exception_message': str(exception)
        },
        exc_info=True
    )
```

### 9.4. Alerting Rules

**Critical Alerts:**

- RabbitMQ connection lost
- MinIO connection failures > 10/hour
- Database connection pool exhausted
- Event processing failure rate > 20%

**Warning Alerts:**

- Error rate > 10% (per platform)
- Processing latency p95 > 10s
- Error spike detected (5x increase)
- Success rate < 90%

**Slack/PagerDuty Integration:**

```python
import requests

def send_alert(severity: str, title: str, message: str):
    """Send alert to Slack/PagerDuty."""
    if severity == 'critical':
        # Send to PagerDuty
        pagerduty_trigger(title, message)

    # Always send to Slack
    slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    requests.post(slack_webhook, json={
        'text': f"[{severity.upper()}] {title}",
        'attachments': [{
            'text': message,
            'color': 'danger' if severity == 'critical' else 'warning'
        }]
    })

# Usage
if error_rate > 10:
    send_alert(
        severity='warning',
        title='High Error Rate Detected',
        message=f'Error rate for {platform}: {error_rate:.2f}%'
    )
```

---

## 10. Migration & Rollout

### 10.1. Backward Compatibility

**During migration period, support both:**

1. **Legacy:** Direct result messages on platform-specific queues (`tiktok_result_queue`, `youtube_result_queue`)
2. **New:** `data.collected` events with MinIO batch fetching

**Implementation Strategy:**

```python
class DualModeProcessor:
    """Support both legacy and new event formats during migration."""

    def __init__(self):
        self.legacy_enabled = True
        self.new_mode_enabled = True

    def process_message(self, message):
        """Auto-detect message type and route accordingly."""

        if 'minio_path' in message.get('payload', {}):
            # New format: data.collected event
            return self.process_new_format(message)
        else:
            # Legacy format: direct result payload
            return self.process_legacy_format(message)

    def process_new_format(self, event):
        """Process data.collected event with MinIO fetch."""
        # Implementation from Section 5
        pass

    def process_legacy_format(self, message):
        """Process legacy direct result message."""
        # Existing legacy implementation
        pass
```

### 10.2. Rollout Phases

**Phase 1: Implementation (2 weeks)**

- Implement `data.collected` consumer
- Implement MinIO batch fetcher
- Implement error code handling
- Implement project ID extraction
- Unit tests & integration tests
- Deploy to development environment

**Phase 2: Testing (1 week)**

- Test with dry-run data (UUID job_ids)
- Test with small projects (100-500 items)
- Validate error handling (inject errors)
- Performance testing (load test with 10,000 items)
- Validate metrics and alerts
- Deploy to staging environment

**Phase 3: Canary Rollout (1 week)**

- Deploy to production (new mode disabled)
- Enable new mode for 10% of traffic
- Monitor metrics (error rate, latency, throughput)
- Compare with legacy mode results
- Fix any issues found

**Phase 4: Full Rollout (1 week)**

- Increase to 50% traffic
- Monitor for 2-3 days
- Increase to 100% traffic
- Monitor for 1 week
- Disable legacy mode processing
- Deprecate legacy queues

**Phase 5: Cleanup (1 week)**

- Remove legacy code
- Update documentation
- Post-deployment review
- Performance optimization

### 10.3. Rollback Plan

**If critical issues arise:**

1. **Immediate Rollback (< 5 minutes):**

   - Disable new mode via feature flag
   - Route all traffic to legacy mode
   - Alert team for investigation

2. **Data Recovery:**

   - Re-process failed batches from MinIO
   - Verify data integrity
   - Update metrics

3. **Root Cause Analysis:**
   - Review logs and metrics
   - Identify failure points
   - Fix issues in development
   - Re-test before retry

**Feature Flag Example:**

```python
class Config:
    NEW_MODE_ENABLED = os.getenv('NEW_MODE_ENABLED', 'false').lower() == 'true'
    LEGACY_MODE_ENABLED = os.getenv('LEGACY_MODE_ENABLED', 'true').lower() == 'true'

# In processing code
if Config.NEW_MODE_ENABLED:
    process_new_format(message)
elif Config.LEGACY_MODE_ENABLED:
    process_legacy_format(message)
else:
    raise RuntimeError("Both modes disabled!")
```

### 10.4. Success Criteria

**Before moving to next phase:**

- [ ] Zero critical errors in current phase
- [ ] Error rate < 5%
- [ ] Success rate > 95%
- [ ] Processing latency p95 < 5s
- [ ] All metrics reporting correctly
- [ ] Alerts functioning properly
- [ ] No data loss detected
- [ ] Team approval to proceed

---

## 11. Support & Resources

### 11.1. Documentation References

**Architecture & Design:**

- Event-Driven Architecture: `document/event-drivent.md`
- Collector Service Behavior: `document/collector-service-behavior.md`
- Crawler Integration Behavior: `document/CRAWLER_INTEGRATION_BEHAVIOR.md`

**Implementation Details:**

- Crawler Refactor Tasks: `openspec/changes/refactor-crawler-event-integration/tasks.md`
- Crawler Review Report: `openspec/changes/refactor-crawler-event-integration/review.md`

### 11.2. Code References (Crawler Implementation)

**Event Publisher:**

- TikTok: `tiktok/internal/infrastructure/rabbitmq/event_publisher.py`
- YouTube: `youtube/internal/infrastructure/rabbitmq/event_publisher.py`

**Batch Upload Logic:**

- TikTok: `tiktok/application/crawler_service.py:544-740`
- YouTube: `youtube/application/crawler_service.py` (similar structure)

**Error Handling:**

- Error Codes: `tiktok/domain/enums.py:71-113`
- Error Builder: `tiktok/utils/errors.py`

**Helper Functions:**

- Project ID Extraction: `tiktok/utils/helpers.py:21-71`
- Result Mapping: `tiktok/utils/helpers.py:200-350`

**Tests (for reference):**

- Batch Upload Tests: `tiktok/tests/integration/test_batch_upload.py`
- Result Publishing Tests: `tiktok/tests/integration/test_result_publishing.py`
- Helper Tests: `tiktok/tests/unit/test_helpers.py`

### 11.3. Environment Examples

**Development:**

```env
RABBITMQ_HOST=localhost
MINIO_ENDPOINT=localhost:9000
DATABASE_URL=postgresql://localhost/analytics_dev
LOG_LEVEL=DEBUG
NEW_MODE_ENABLED=true
LEGACY_MODE_ENABLED=true
```

**Staging:**

```env
RABBITMQ_HOST=rabbitmq-staging
MINIO_ENDPOINT=minio-staging:9000
DATABASE_URL=postgresql://postgres-staging/analytics
LOG_LEVEL=INFO
NEW_MODE_ENABLED=true
LEGACY_MODE_ENABLED=true
ERROR_ALERT_THRESHOLD=15
```

**Production:**

```env
RABBITMQ_HOST=rabbitmq-prod
MINIO_ENDPOINT=minio-prod:9000
DATABASE_URL=postgresql://postgres-prod/analytics
LOG_LEVEL=INFO
NEW_MODE_ENABLED=true
LEGACY_MODE_ENABLED=false
ERROR_ALERT_THRESHOLD=10
METRICS_ENABLED=true
```

### 11.4. Troubleshooting Guide

**Common Issues:**

| Issue               | Possible Cause          | Solution                                                               |
| ------------------- | ----------------------- | ---------------------------------------------------------------------- |
| Events not received | Queue binding incorrect | Check queue binding to `smap.events` with routing key `data.collected` |
| MinIO fetch fails   | Invalid credentials     | Verify `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`                       |
| Decompression error | Missing zstd library    | Install `pip install zstandard`                                        |
| High error rate     | Upstream crawler issues | Check crawler service logs and health                                  |
| Processing timeout  | Batch too large         | Increase timeout or reduce concurrent batches                          |
| Database deadlock   | Concurrent writes       | Use batch inserts with proper locking                                  |

### 11.5. Contact Information

**For Questions:**

- Crawler Team: (contact info)
- Infrastructure Team: (contact info)
- Analytics Team Lead: (contact info)

**Support Channels:**

- Slack: #analytics-service
- Email: analytics-support@company.com
- On-call: (PagerDuty rotation)

---

## Appendix A: Complete Data Flow Diagram

```
┌──────────────┐
│ User Executes│
│   Project    │
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Project Service                            │
│ - Publishes project.created event          │
└──────┬─────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Collector Service                          │
│ - Receives project.created                 │
│ - Dispatches crawler jobs                  │
└──────┬─────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Crawler Service (TikTok/YouTube)           │
│ - Crawls content in batches                │
│ - Every 50 (TikTok) / 20 (YouTube) items:  │
│   ├─ Upload batch to MinIO                 │
│   └─ Publish data.collected event          │
└──────┬─────────────────────────────────────┘
       │
       ▼ (smap.events exchange)
       │ (routing key: data.collected)
       │
       ▼
┌────────────────────────────────────────────┐
│ Analytics Service (YOU ARE HERE)           │
│ 1. Receive data.collected event            │
│ 2. Extract minio_path from event           │
│ 3. Fetch batch from MinIO                  │
│ 4. Parse JSON array of items               │
│ 5. Extract project_id from job_id          │
│ 6. Process each item:                      │
│    ├─ Success: Store content/author/       │
│    │           comments                     │
│    └─ Error: Log error, update metrics     │
│ 7. Update analytics database                │
│ 8. Update progress metrics                  │
│ 9. Acknowledge RabbitMQ message             │
└──────┬─────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Dashboard / User Interface                 │
│ - Displays processed analytics             │
│ - Shows project progress                   │
│ - Visualizes content insights              │
└────────────────────────────────────────────┘
```

---

## Appendix B: Quick Start Guide

**Step 1: Install Dependencies**

```bash
pip install pika boto3 zstandard sqlalchemy pydantic-settings
```

**Step 2: Configure Environment**

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Step 3: Run Consumer**

```python
from analytics_consumer import DataCollectedConsumer

consumer = DataCollectedConsumer(
    rabbitmq_url='amqp://user:pass@rabbitmq:5672/'
)
consumer.connect()
consumer.start_consuming()
```

**Step 4: Monitor Metrics**

```bash
# Metrics available at http://localhost:9090/metrics
curl http://localhost:9090/metrics | grep analytics_
```

**Step 5: View Logs**

```bash
tail -f logs/analytics.log | grep -E "(Received|Processed|Error)"
```

---

**End of Document**

**Version:** 1.0
**Last Updated:** 2025-12-06
**Next Review:** 2026-01-06

For questions or clarifications, contact the Crawler Team or refer to the documentation links in Section 11.
