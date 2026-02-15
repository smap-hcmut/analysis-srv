# SMAP Analytics Service

Analytics engine for SMAP platform: consumes social media crawl events from RabbitMQ, runs NLP pipeline (sentiment, intent, keywords, impact), and persists results to PostgreSQL.

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐
│  Crawler /  │     │    RabbitMQ      │     │   Analytics Consumer            │
│  n8n / API  │────▶│ smap.events      │────▶│   (this service)                │
│             │     │ data.collected   │     │                                 │
└─────────────┘     └──────────────────┘     └─────────────┬───────────────────┘
                                                           │
                        ┌──────────────────────────────────┼──────────────────┐
                        ▼                  ▼               ▼                  ▼
                 ┌──────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                 │ PostgreSQL   │   │   Redis     │   │   MinIO     │   │ SpaCy-YAKE /│
                 │schema_analyst│   │   (cache)   │   │ (batch raw) │   │ PhoBERT     │
                 └──────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

**Single service:**

- **Consumer Service**: RabbitMQ consumer that subscribes to `analytics.data.collected`, runs the 5-stage analytics pipeline (preprocess → intent → keywords → sentiment → impact), and writes to `schema_analyst.analyzed_posts`.

**Note**: API layer (FastAPI health/metrics) is planned; current entry point is consumer only.

---

## Tech Stack

| Component       | Technology             | Purpose                          |
| --------------- | ---------------------- | -------------------------------- |
| Language        | Python 3.12+           | Backend                          |
| Package manager | uv                     | Dependencies, lock file          |
| Message queue   | RabbitMQ (aio-pika)    | Event-driven analytics           |
| Database        | PostgreSQL             | Analyzed posts (schema_analyst)  |
| ORM             | SQLAlchemy 2.x (async) | Async persistence                |
| Cache / storage | Redis, MinIO           | Cache, batch raw data (optional) |
| Sentiment       | PhoBERT (ONNX)         | Vietnamese sentiment             |
| Keywords        | YAKE + spaCy           | Keyword extraction, NER          |
| Config          | YAML + env             | config/config.yaml               |

---

## Features

- **Event-driven pipeline**: Consume `data.collected` from RabbitMQ; support inline payload or `minio_path` batch.
- **5-stage analytics**: Text preprocessing → Intent classification → Keyword extraction → Sentiment analysis (PhoBERT) → Impact calculation.
- **Persistence**: Async insert/update into `schema_analyst.analyzed_posts` with full crawler and AI result fields.
- **Domain-driven design**: Clear separation: analytics (orchestrator), analyzed_post (repository), sentiment/intent/keyword/impact (AI domains), consumer (infrastructure).
- **Configurable**: YAML config for DB, RabbitMQ queues, PhoBERT, YAKE, impact weights, batch size, retries.
- **Graceful shutdown**: SIGTERM/SIGINT handled; in-flight message processed before exit.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- PostgreSQL 15+ (schema `schema_analyst` must exist)
- RabbitMQ
- Redis (optional, for cache)
- MinIO (optional, for batch payloads)

### 1. Clone & Configure

```bash
git clone <repository-url>
cd analysis-srv

# Install dependencies (uv)
uv sync

# Copy and edit config
cp config/config.yaml config/config.local.yaml
# Edit database URL, RabbitMQ URL, Redis, MinIO, etc.
```

**Optional**: Use env vars to override config (see [Configuration](#configuration)).

### 2. Setup Database

```bash
# Create schema if not exists (as DB superuser or analyst_master)
psql -h localhost -U postgres -d smap -c "CREATE SCHEMA IF NOT EXISTS schema_analyst;"

# Run migration (creates schema_analyst.analyzed_posts)
uv run python scripts/run_migration.py migration/001_create_analyzed_posts_table.sql

# Or with custom URL
uv run python scripts/run_migration.py migration/001_create_analyzed_posts_table.sql "postgresql://user:pass@host:5432/smap"
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
# Send a test message to RabbitMQ (adjust URL in script if needed)
uv run python scripts/test_analytics_message.py

# Check logs for "[AnalyticsHandler] Message processed" and DB for new row in schema_analyst.analyzed_posts
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
  schema: "schema_analyst"
  pool_size: 20
  max_overflow: 10

rabbitmq:
  url: "amqp://admin:password@host:5672/"
  prefetch_count: 1
  queues:
    - name: "analytics.data.collected"
      exchange: "smap.events"
      routing_key: "data.collected"
      handler_module: "internal.analytics.delivery.rabbitmq.consumer.handler"
      handler_class: "AnalyticsHandler"
      prefetch_count: 1
      enabled: true
  publish:
    exchange: "results.inbound"
    routing_key: "analyze.result"
    enabled: true

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

Config is loaded by `config.config.load_config()` from YAML and optional env (e.g. `DATABASE_URL`, `RABBITMQ_URL`). See `config/config.py` for all keys and `ConfigLoader`.

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

- **Required**: Either `payload.meta` (inline post) or `payload.minio_path` (batch).
- **Output**: Rows in `schema_analyst.analyzed_posts` with IDs from `meta.id`, plus sentiment, intent, keywords, impact (when AI stages are enabled).

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
│   │   └── delivery/rabbitmq/consumer/  # AnalyticsHandler (message adapter)
│   ├── analyzed_post/     # Persistence: usecase, repository (PostgreSQL)
│   ├── sentiment_analysis/ # PhoBERT sentiment (usecase, interface)
│   ├── intent_classification/ # Intent patterns (usecase, interface)
│   ├── keyword_extraction/   # YAKE + spaCy (usecase, interface)
│   ├── impact_calculation/   # Impact score (usecase, interface)
│   ├── text_preprocessing/   # Text normalization (usecase, interface)
│   ├── consumer/           # ConsumerServer, ConsumerRegistry, Dependencies
│   └── model/             # SQLAlchemy models (analyzed_post), PhoBERT assets
├── pkg/                    # Shared infrastructure
│   ├── logger/             # Structured logging
│   ├── postgre/            # Async PostgreSQL (asyncpg, SQLAlchemy)
│   ├── redis/              # Redis client
│   ├── rabbitmq/           # aio-pika consumer
│   ├── minio/              # MinIO client + compression
│   ├── zstd/               # Zstd compression
│   ├── phobert_onnx/       # PhoBERT ONNX inference
│   └── spacy_yake/         # SpaCy + YAKE keyword extraction
├── migration/              # SQL migrations (schema_analyst)
├── scripts/                # run_migration.py, test_analytics_message.py
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
  -e RABBITMQ_URL="amqp://..." \
  analysis-srv:latest
```

### Environment variables

Override config via env when running in production (see `ConfigLoader` for supported keys), e.g.:

- `DATABASE_URL`, `RABBITMQ_URL`, `REDIS_HOST`, `MINIO_ENDPOINT`, etc.

---

## Security

- **Credentials**: Do not commit `config.local.yaml` or secrets; use env or secret manager in production.
- **DB**: Use least-privilege user (`analyst_prod`) for runtime; reserve `analyst_master` for migrations.
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
