# SMAP Analytics Service

Analytics engine for SMAP platform: consumes social media crawl events from Kafka, runs NLP pipeline (sentiment, intent, keywords, impact), and persists results to PostgreSQL + publishes enriched output to Kafka.

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐
│  Collector  │     │      Kafka       │     │   Analytics Consumer            │
│  Service    │────▶│ smap.collector   │────▶│   (this service)                │
│             │     │    .output       │     │                                 │
└─────────────┘     └──────────────────┘     └─────────────┬───────────────────┘
                                                           │
                        ┌──────────────────────────────────┼──────────────────┐
                        ▼                  ▼               ▼                  ▼
                 ┌──────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                 │ PostgreSQL   │   │   Kafka     │   │   MinIO     │   │ SpaCy-YAKE /│
                 │  analytics   │   │  (output)   │   │ (batch raw) │   │ PhoBERT     │
                 └──────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

**Single service:**

- **Consumer Service**: Kafka consumer that subscribes to `smap.collector.output` (UAP v1.0 format), runs the 5-stage analytics pipeline (preprocess → intent → keywords → sentiment → impact), writes to `analytics.post_analytics`, and publishes enriched output to Kafka topic `smap.analytics.output`.

**Note**: API layer (FastAPI health/metrics) is planned; current entry point is Kafka consumer only.

---

## Tech Stack

| Component       | Technology             | Purpose                           |
| --------------- | ---------------------- | --------------------------------- |
| Language        | Python 3.12+           | Backend                           |
| Package manager | uv                     | Dependencies, lock file           |
| Message queue   | Kafka (aiokafka)       | Event-driven analytics (I/O)      |
| Database        | PostgreSQL             | Analyzed posts (analytics schema) |
| ORM             | SQLAlchemy 2.x (async) | Async persistence                 |
| Cache / storage | Redis, MinIO           | Cache, batch raw data (optional)  |
| Sentiment       | PhoBERT (ONNX)         | Vietnamese sentiment              |
| Keywords        | YAKE + spaCy           | Keyword extraction, NER           |
| Config          | YAML + env             | config/config.yaml                |

---

## Features

- **Event-driven pipeline**: Consume UAP v1.0 messages from Kafka `smap.collector.output`; support inline payload or `minio_path` batch.
- **5-stage analytics**: Text preprocessing → Intent classification → Keyword extraction → Sentiment analysis (PhoBERT) → Impact calculation.
- **Persistence**: Async insert/update into `analytics.post_analytics` with full crawler and AI result fields.
- **Output publishing**: Publish enriched output (batch array) to Kafka topic `smap.analytics.output` for Knowledge Service.
- **Domain-driven design**: Clear separation: analytics (orchestrator), analyzed_post (repository), sentiment/intent/keyword/impact (AI domains), consumer (infrastructure).
- **Configurable**: YAML config for DB, Kafka consumer/producer, PhoBERT, YAKE, impact weights, batch size, retries.
- **Graceful shutdown**: SIGTERM/SIGINT handled; in-flight message processed before exit.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- PostgreSQL 15+ (schema `analytics` must exist)
- Kafka (input + output topics)
- Redis (optional, for cache)
- MinIO (optional, for batch payloads)

### 1. Clone & Configure

```bash
git clone <repository-url>
cd analysis-srv

# Install dependencies (uv)
uv sync

# Copy and edit config
cp config/config.yaml.example config/config.yaml
# Edit database URL, Kafka bootstrap servers, Redis, MinIO, etc.
```

**Optional**: Use env vars to override config (see [Configuration](#configuration)).

### 2. Setup Database

```bash
# Create schema if not exists (as DB superuser or analyst_master)
psql -h localhost -U postgres -d smap -c "CREATE SCHEMA IF NOT EXISTS analytics;"

# Run migration (creates analytics.post_analytics)
uv run python scripts/run_migration.py migration/003_create_post_analytics.sql

# Or with custom URL
uv run python scripts/run_migration.py migration/003_create_post_analytics.sql "postgresql://user:pass@host:5432/smap"
```

**Note**: Default migration script uses `analyst_master`; runtime uses `analyst_prod` (SELECT/INSERT/UPDATE/DELETE). Adjust users and grants per environment.

### 3. SpaCy model (keyword extraction)

```bash
make spacy-model
# or: uv run python -m spacy download xx_ent_wiki_sm
```

### 4. Run Consumer

```bash
# Development
make run-consumer

# Or directly
uv run python -m apps.consumer.main
```

### 5. Test

```bash
# Send a test message to Kafka (adjust broker URL in script if needed)
# Note: Test script needs to be updated for Kafka
# uv run python scripts/test_analytics_message.py

# Check logs for "[KafkaHandler] Message processed" and DB for new row in analytics.post_analytics
```

---

## Configuration

Key settings in `config/config.yaml` (and optional env overrides):

```yaml
service:
  name: "analytics-engine"
  version: "0.1.0"
  environment: "development"

database:
  url: "postgresql+asyncpg://analyst_prod:analyst_prod_pwd@host:5432/smap"
  url_sync: "postgresql://analyst_prod:analyst_prod_pwd@host:5432/smap"
  schema: "analytics"
  pool_size: 20
  max_overflow: 10

kafka:
  bootstrap_servers: "172.16.21.206:9092"
  
  consumer:
    group_id: "analytics-service"
    topics:
      - "smap.collector.output"
    auto_offset_reset: "earliest"
    enable_auto_commit: false
    max_poll_records: 10
    session_timeout_ms: 30000
    heartbeat_interval_ms: 10000
  
  producer:
    topic: "smap.analytics.output"
    acks: "all"
    compression_type: "gzip"
    enable_idempotence: true
    batch_publish_size: 10
    linger_ms: 100
    max_in_flight_requests: 5

phobert:
  model_path: "internal/model/phobert"
  max_length: 256

keyword_extraction:
  spacy_model: "xx_ent_wiki_sm"
  yake_language: "vi"
  yake_max_keywords: 30
  max_keywords: 30

intent_classifier:
  enabled: true
  confidence_threshold: 0.5
  patterns_path: "config/intent_patterns.yaml"

impact:
  weight:
    view: 0.01
    like: 1.0
    comment: 2.0
    save: 3.0
    share: 5.0
  platform:
    tiktok: 1.0
    facebook: 1.2
    youtube: 1.5
    unknown: 1.0
  threshold:
    viral: 70.0
    kol_followers: 50000
```

Config is loaded by `config.config.load_config()` from YAML and optional env (e.g. `DATABASE_URL`, `KAFKA_BOOTSTRAP_SERVERS`). See `config/config.py` for all keys and `ConfigLoader`.

---

## Message Format (Input)

Consumer expects a JSON envelope on the queue:

```json
{
  "event_id": "evt_123",
  "event_type": "data.collected",
  "timestamp": "2026-02-15T10:00:00Z",
  "payload": {
    "project_id": "uuid",
    "job_id": "uuid-suffix",
    "batch_index": 1,
    "content_count": 50,
    "platform": "tiktok",
    "task_type": "crawl",
    "brand_name": "Brand",
    "keyword": "search term",
    "minio_path": "s3://bucket/path/to/batch.json",
    "meta": {
      "id": "post_123",
      "platform": "tiktok",
      "permalink": "...",
      "published_at": "..."
    },
    "content": {
      "text": "...",
      "transcription": "",
      "duration": 30,
      "hashtags": []
    },
    "interaction": {
      "views": 0,
      "likes": 0,
      "comments_count": 0,
      "shares": 0,
      "saves": 0
    },
    "author": {
      "id": "...",
      "name": "...",
      "username": "...",
      "avatar_url": "...",
      "followers": 0,
      "is_verified": false
    },
    "comments": []
  }
}
```

- **Required**: UAP v1.0 format with `ingest`, `content`, `signals` blocks.
- **Output**: Rows in `analytics.post_analytics` with enriched fields, plus Kafka message to `smap.analytics.output`.

---

## Project Structure

```
analysis-srv/
├── apps/
│   └── consumer/           # Consumer entrypoint (main.py, Dockerfile)
├── config/                 # config.yaml, config.py (ConfigLoader)
├── internal/
│   ├── analytics/         # Orchestration: pipeline, handler, types, constants
│   │   ├── usecase/       # AnalyticsPipeline (5-stage orchestration)
│   │   └── delivery/      # Message adapters (Kafka consumer/producer)
│   │       ├── kafka/     # Kafka consumer handler + producer
│   │       └── rabbitmq/  # UAP parser (reused, broker-agnostic)
│   ├── analyzed_post/     # Persistence: usecase, repository (PostgreSQL)
│   ├── sentiment_analysis/ # PhoBERT sentiment (usecase, interface)
│   ├── intent_classification/ # Intent patterns (usecase, interface)
│   ├── keyword_extraction/   # YAKE + spaCy (usecase, interface)
│   ├── impact_calculation/   # Impact score (usecase, interface)
│   ├── text_preprocessing/   # Text normalization (usecase, interface)
│   ├── consumer/           # KafkaConsumerServer, ConsumerRegistry, Dependencies
│   └── model/             # SQLAlchemy models (analyzed_post), PhoBERT assets
├── pkg/                    # Shared infrastructure
│   ├── logger/             # Structured logging
│   ├── postgre/            # Async PostgreSQL (asyncpg, SQLAlchemy)
│   ├── redis/              # Redis client
│   ├── kafka/              # Kafka consumer/producer (aiokafka)
│   ├── rabbitmq/           # aio-pika consumer (kept as reusable package)
│   ├── minio/              # MinIO client + compression
│   ├── zstd/               # Zstd compression
│   ├── phobert_onnx/       # PhoBERT ONNX inference
│   └── spacy_yake/         # SpaCy + YAKE keyword extraction
├── migration/              # SQL migrations (analytics schema)
├── scripts/                # run_migration.py, test scripts
└── documents/              # IMPLEMENTATION_STATUS.md, etc.
```

---

## Development

```bash
# Install
make install   # or: uv sync

# Run consumer
make run-consumer

# Lint & format
make lint
make format

# Tests (placeholder)
make test

# SpaCy
make spacy-model
make spacy-list

# Clean caches
make clean
```

---

## Deployment

### Docker

```bash
# Build (from repo root; Dockerfile uses multi-stage, installs deps + SpaCy model)
docker build -t analysis-srv:latest -f apps/consumer/Dockerfile .

# Run (mount config and set env as needed)
docker run -d -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e KAFKA_BOOTSTRAP_SERVERS="..." \
  analysis-srv:latest
```

### Environment variables

Override config via env when running in production (see `ConfigLoader` for supported keys), e.g.:

- `DATABASE_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `REDIS_HOST`, `MINIO_ENDPOINT`, etc.

---

## Security

- **Credentials**: Do not commit `config.local.yaml` or secrets; use env or secret manager in production.
- **DB**: Use least-privilege user (`analyst_prod`) for runtime; reserve `analyst_master` for migrations.
- **Network**: Restrict Kafka and PostgreSQL access to trusted networks/VPC.
- **Network**: Restrict RabbitMQ and PostgreSQL access to trusted networks/VPC.

---

## Documentation

- [Implementation Status](documents/IMPLEMENTATION_STATUS.md) — Architecture, data flow, TODO (AI modules, batch, API, tests)
- Internal domain READMEs: `internal/analytics/README.md`, `internal/sentiment_analysis/README.md`, `internal/keyword_extraction/README.md`, `internal/intent_classification/README.md`, `internal/impact_calculation/README.md`

---

## License

Part of SMAP graduation project.

---

**Version**: 0.1.0  
**Last Updated**: 15/02/2026
