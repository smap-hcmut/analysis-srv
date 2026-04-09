# analysis-srv — SMAP Analytics Service

Event-driven NLP analytics engine for the SMAP social media monitoring platform. Consumes raw social media crawl events from Kafka (UAP v1.0 format), runs a multi-phase analysis pipeline (normalization → dedup → spam → threads → NLP enrichment → enrichment → review → reporting → crisis detection), persists structured insights to PostgreSQL, and publishes enriched output to Kafka for downstream consumers.

> **Graduation project** — HCMUT / SMAP Platform

---

## Architecture

See [`architecture.excalidraw`](./architecture.excalidraw) for the full interactive diagram.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  SMAP Analytics Service  (analysis-srv)                                         │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  ConsumerServer (apps/consumer)                                            │ │
│  │  ConsumerRegistry · KafkaConsumer (aiokafka) · SIGTERM graceful shutdown  │ │
│  └─────────────────────────────────┬──────────────────────────────────────────┘ │
│                                    │ parse UAP → IngestedBatchBundle             │
│                                    ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  Phase 3–6 Pipeline  (asyncio.to_thread · batch mode · PipelineConfig)    │ │
│  │                                                                            │ │
│  │  1. Normalization    UAP → MentionRecord, lang detect, quality flags       │ │
│  │  2. Dedup            MinHash LSH (64 perms, 16 bands, 0.82 threshold)      │ │
│  │  3. Spam Detection   Inorganic author scoring, quality_weight              │ │
│  │  4. Thread Topology  Root/parent/child graph, reply depth                  │ │
│  │  5. NLP Enrichment   NLPBatchEnricher: preprocessing → intent → keywords   │ │
│  │                      → sentiment (PhoBERT ONNX) → impact → NLPFact[]       │ │
│  │  6. Enrichment       NER, semantic topics (Phase 4)                        │ │
│  │  7. Review Queue     Low-confidence facts for human review                 │ │
│  │  8. Reporting        BI bundles: SOV, Buzz, Emerging (Phase 5)             │ │
│  │  9. Crisis Detection Rule-based, composite score, CrisisLevel (Phase 6)   │ │
│  └─────────────────────────────────┬──────────────────────────────────────────┘ │
│                                    │ list[NLPFact]                               │
│                                    ▼ _persist_and_publish()                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │  Contract Publisher  (internal/contract_publisher)                          │ │
│  │  analytics.batch.completed · analytics.insights.published                  │ │
│  │  analytics.report.digest                    + post_insight write (PG)      │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Storage / pkg/                                                          │   │
│  │  PostgreSQL (schema_analysis)  ·  Redis (cache)  ·  MinIO (crawl-results│   │
│  │  Prometheus metrics  ·  Kafka Producer (idempotent · gzip · acks=all)   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
         ▲                                               │
         │ UAP v1.0                                      │ enriched output
  [Collector Service]                           [Knowledge Service]
  smap.collector.output                         (downstream RAG)
```

---

## Pipeline Design

Every Kafka message flows through a single unified pipeline:

```
Kafka message
→ ConsumerServer._handle_message()
→ parse UAP → IngestedBatchBundle
→ asyncio.to_thread(pipeline.run)
    STAGE_NORMALIZATION  → list[MentionRecord]
    STAGE_DEDUP          → MinHash clusters
    STAGE_SPAM           → spam scores / quality_weight
    STAGE_THREADS        → ThreadBundle
    STAGE_NLP            → NLPBatchEnricher.enrich_batch() → list[NLPFact]
    STAGE_ENRICHMENT     → EnrichmentBundle  (Phase 4)
    STAGE_REVIEW         → ReviewQueue       (Phase 4)
    STAGE_REPORTING      → BIReportBundle    (Phase 5)
    STAGE_CRISIS         → CrisisAssessment  (Phase 6)
→ _persist_and_publish(nlp_facts):
    for each NLPFact:
        post_insight_usecase.create(...)   ← PostgreSQL
        contract_publisher.publish_one(...)← Kafka (3 topics)
```

Pipeline phases are **feature-flag controlled** via `PipelineConfig`:

```python
PipelineConfig(
    enable_normalization=True,
    enable_dedup=True,
    enable_spam=True,
    enable_threads=True,
    enable_nlp=True,        # STAGE_NLP — NLPBatchEnricher
    enable_enrichment=False,
    enable_review=False,
    enable_reporting=False,
    enable_crisis=False,
)
```

---

## Pipeline Stages

| Stage | Phase | Module | Description |
|---|---|---|---|
| 1. Normalization | 3 | `internal/normalization` | UAP → `MentionRecord` silver layer; lang detect, quality flags, hashtags/URLs |
| 2. Dedup | 3 | `internal/dedup` | MinHash LSH; 64 perms, 16 bands, 0.82 similarity threshold |
| 3. Spam Detection | 3 | `internal/spam` | Inorganic author scoring, `quality_weight`, suspicion flags |
| 4. Thread Topology | 3 | `internal/threads` | Root/parent/child graph, reply depth, sibling IDs |
| 5. NLP Enrichment | 3–6 | `internal/analytics/usecase/batch_enricher` | `NLPBatchEnricher`: preprocessing → intent → keywords → sentiment (PhoBERT ONNX) → impact → `NLPFact[]` |
| 6. Enrichment | 4 | `internal/enrichment` | NER, semantic topics, entity/topic fact stubs |
| 7. Review Queue | 4 | `internal/review` | Low-confidence facts enqueued for human review |
| 8. Reporting | 5 | `internal/reporting` | BI bundles: SOV, Buzz, Emerging, Issues; Polars DataFrames |
| 9. Crisis Detection | 6 | `internal/crisis` | Rule-based, composite score, `CrisisLevel` enum |

### NLP Enrichment sub-stages (inside STAGE_NLP)

| Sub-stage | Module | Description |
|---|---|---|
| Text Preprocessing | `internal/text_preprocessing` | Spam filter, clean text, language detection |
| Intent Classification | `internal/intent_classification` | YAML pattern rules, confidence threshold 0.5 |
| Keyword Extraction | `internal/keyword_extraction` | YAKE statistical + SpaCy NER (`xx_ent_wiki_sm`) |
| Sentiment Analysis | `internal/sentiment_analysis` | PhoBERT ONNX, Vietnamese 3-class (PyVi tokenizer) |
| Impact Calculation | `internal/impact_calculation` | Engagement score, risk level, KOL flag |

---

## Project Structure

```
analysis-srv/
├── apps/
│   └── consumer/               # Entry point: main.py, Dockerfile
├── config/
│   ├── config.py               # ConfigLoader (YAML + env, Viper-style priority)
│   ├── config.yaml             # Runtime configuration
│   └── intent_patterns.yaml    # Intent classification rules
├── internal/
│   ├── analytics/              # NLPBatchEnricher (5-stage NLP inside STAGE_NLP)
│   │   ├── usecase/
│   │   │   ├── batch_enricher.py   # NLPBatchEnricher + to_post_insight_input()
│   │   │   └── helpers.py          # normalize_platform, add_uap_metadata
│   │   ├── type.py                 # AnalyticsResult, Input, Output, Config
│   │   ├── constant.py             # NLP constants
│   │   └── interface.py            # IContractPublisher Protocol
│   ├── builder/                # InsightMessage assembler (UAP + AnalyticsResult → output DTO)
│   ├── consumer/               # ConsumerServer, ConsumerRegistry (DI wiring)
│   ├── contract_publisher/     # 3-topic Kafka publisher contract (v1.2)
│   ├── crisis/                 # Phase 6: rule-based crisis detection
│   ├── dedup/                  # MinHash LSH near-duplicate detection
│   ├── enrichment/             # Phase 4: NER, semantic topics
│   ├── impact_calculation/     # Engagement score, risk level, KOL flag
│   ├── ingestion/              # UAP → IngestedBatchBundle adapter
│   ├── intent_classification/  # YAML pattern-based intent classifier
│   ├── keyword_extraction/     # YAKE + SpaCy NER
│   ├── model/                  # UAPRecord, InsightMessage, PostInsight ORM, constants
│   ├── normalization/          # UAP → MentionRecord (silver layer)
│   ├── observability/          # Prometheus metrics (no-op fallback)
│   ├── outbox/                 # Transactional outbox (analytics_outbox table)
│   ├── pipeline/               # Phase 3–6 pipeline runner + PipelineConfig/Services
│   ├── post_insight/           # PostgreSQL persistence (post_insight CRUD)
│   ├── reporting/              # Phase 5: BI reports, insight cards, Polars DataFrames
│   ├── review/                 # Low-confidence fact review queue
│   ├── runtime/                # RunContext, OntologyConfig, EnumRegistry
│   ├── sentiment_analysis/     # PhoBERT ONNX wrapper domain usecase
│   ├── spam/                   # Inorganic author/mention scoring
│   ├── text_preprocessing/     # Text normalization
│   └── threads/                # Thread topology (root/parent/child graph)
├── pkg/
│   ├── kafka/                  # aiokafka consumer + producer, errors, interfaces
│   ├── minio/                  # MinIO S3-compatible adapter (Zstd auto-detect)
│   ├── phobert_onnx/           # PhoBERT ONNX inference (optimum[onnxruntime])
│   ├── postgre/                # SQLAlchemy 2.x async + asyncpg, connection pooling
│   ├── rabbitmq/               # aio-pika (kept as reusable package, unused in prod)
│   ├── redis/                  # redis-py async client, JSON serialization
│   ├── spacy_yake/             # SpaCy NER + YAKE keyword extractor (cascade fallback)
│   ├── time_utils.py           # utc_now_iso(), datetime_to_iso() canonical helpers
│   └── zstd/                   # Zstandard compression wrapper
├── migration/
│   ├── 001_create_analytics_outbox.sql
│   ├── 002_create_analytics_run_manifest.sql
│   └── 003_create_post_analytics.sql
├── scripts/
│   ├── run_migration.py        # Migration runner (reads ANALYTICS_DATABASE_URL env)
│   └── replay_batch.py         # Dev tool: replay a batch through the full pipeline
├── tests/                      # Pytest unit tests (180 tests)
├── documents/                  # Architecture specs, implementation status
├── manifests/                  # Kubernetes manifests
├── pyproject.toml              # uv + hatchling project definition
└── Makefile
```

---

## Kafka Topics

| Topic | Direction | Format | Description |
|---|---|---|---|
| `smap.collector.output` | **Consumed** | UAP v1.0 JSON | Raw social media crawl events from Collector Service |
| `analytics.batch.completed` | **Published** | InsightMessage | Per-document enriched batch feed to Knowledge Service |
| `analytics.insights.published` | **Published** | InsightCard | Insight cards from Phase 5 reporting |
| `analytics.report.digest` | **Published** | BIReportBundle | BI report digests (SOV, Buzz, Emerging, etc.) |

Consumer group: `analytics-service`. Manual offset commit (`enable_auto_commit=False`).
Producer: idempotent, gzip, `acks=all`, `linger_ms=100`.

---

## Storage

| System | Library | Usage |
|---|---|---|
| **PostgreSQL 15+** | SQLAlchemy 2.x async + asyncpg | Primary persistence. Schema `schema_analysis`. Pool: 20 connections, max_overflow 10. |
| **MinIO** | `minio` SDK | S3-compatible object store. Bucket `crawl-results`. Auto-detects Zstd compression from metadata. |
| **Redis** | `redis-py` async | Optional cache layer. Health-checked on startup. |
| **Kafka** | `aiokafka` | Input consumer + output producer. Snappy/gzip/lz4/zstd codecs supported. |

### PostgreSQL Tables

| Table | Schema | Description |
|---|---|---|
| `post_insight` | `schema_analysis` | Main NLP results: sentiment, keywords, ABSA aspects (JSONB), risk, engagement |
| `analytics_outbox` | `schema_analysis` | Transactional outbox for exactly-once Kafka delivery (Phase 6) |
| `analytics_run_manifest` | `schema_analysis` | Audit log for pipeline runs |

---

## Configuration

Config priority: **env vars** > `.env` file > `config/config.yaml`.

All env vars use the `ANALYTICS_` prefix unless noted.

```yaml
# config/config.yaml (key sections)

database:
  url: "postgresql+asyncpg://analyst_prod:password@host:5432/smap"
  schema: "schema_analysis"
  pool_size: 20
  max_overflow: 10

kafka:
  bootstrap_servers: "kafka:9092"
  consumer:
    group_id: "analytics-service"
    topics: ["smap.collector.output"]
    auto_offset_reset: "earliest"
    enable_auto_commit: false
  producer:
    acks: "all"
    compression_type: "gzip"
    enable_idempotence: true
    linger_ms: 100

minio:
  endpoint: ""            # set via ANALYTICS_MINIO_ENDPOINT
  access_key: ""          # set via ANALYTICS_MINIO_ACCESS_KEY
  secret_key: ""          # set via ANALYTICS_MINIO_SECRET_KEY
  crawl_results_bucket: "crawl-results"

phobert:
  model_path: "internal/model/phobert"
  max_length: 256

impact:
  weight: { view: 0.01, like: 1.0, comment: 2.0, save: 3.0, share: 5.0 }
  platform: { tiktok: 1.0, facebook: 1.2, youtube: 1.5 }
  threshold: { viral: 70.0, kol_followers: 50000 }

contract_publisher:
  enabled: true
  batch_size: 100
  flush_interval_seconds: 30
```

**Required env vars for production:**

```bash
ANALYTICS_DATABASE_URL=postgresql+asyncpg://...
ANALYTICS_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ANALYTICS_MINIO_ENDPOINT=minio:9000
ANALYTICS_MINIO_ACCESS_KEY=...
ANALYTICS_MINIO_SECRET_KEY=...
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) package manager
- PostgreSQL 15+ with `schema_analysis` schema
- Kafka broker
- Redis (optional)
- MinIO (optional, for batch payloads stored as objects)

### 1. Install

```bash
git clone <repository-url>
cd analysis-srv

uv sync
```

### 2. Configure

```bash
cp config/config.yaml.example config/config.yaml
# Edit database URL, Kafka bootstrap servers, MinIO credentials, etc.
# Or set ANALYTICS_* environment variables
```

### 3. Run migrations

```bash
# Requires ANALYTICS_DATABASE_URL or DATABASE_URL env var, or --db-url flag
uv run python scripts/run_migration.py migration/001_create_analytics_outbox.sql
uv run python scripts/run_migration.py migration/002_create_analytics_run_manifest.sql
uv run python scripts/run_migration.py migration/003_create_post_analytics.sql

# Custom URL
uv run python scripts/run_migration.py migration/003_create_post_analytics.sql \
  --db-url "postgresql://user:pass@host:5432/smap"
```

### 4. Download SpaCy model

```bash
make spacy-model
# or: uv run python -m spacy download xx_ent_wiki_sm
```

### 5. Run the consumer

```bash
# Development
make run-consumer

# Direct
uv run consumer
# or: uv run python -m apps.consumer.main
```

---

## Development

```bash
# Install dependencies
make install       # uv sync

# Run consumer
make run-consumer

# Lint + format
make lint
make format

# Tests
make test          # uv run pytest tests/ -q  (180 tests)

# SpaCy
make spacy-model   # download xx_ent_wiki_sm
make spacy-list    # list installed models

# Clean caches
make clean
```

### Running tests

```bash
uv run pytest tests/ -q
# 180 passed in ~0.82s
```

Tests are unit tests only — no external dependencies (Kafka, PostgreSQL, MinIO) required.

---

## Docker

```bash
# Build
docker build -t analysis-srv:latest -f apps/consumer/Dockerfile .

# Run
docker run -d \
  -e ANALYTICS_DATABASE_URL="postgresql+asyncpg://..." \
  -e ANALYTICS_KAFKA_BOOTSTRAP_SERVERS="kafka:9092" \
  -e ANALYTICS_MINIO_ENDPOINT="minio:9000" \
  -e ANALYTICS_MINIO_ACCESS_KEY="..." \
  -e ANALYTICS_MINIO_SECRET_KEY="..." \
  -v $(pwd)/config:/app/config \
  analysis-srv:latest
```

Kubernetes manifests are in `manifests/`.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Package manager | uv + hatchling |
| Message queue | Kafka (aiokafka) |
| Database | PostgreSQL 15+ (asyncpg + SQLAlchemy 2.x async) |
| Cache | Redis (redis-py async) |
| Object storage | MinIO (S3-compatible) |
| Sentiment | PhoBERT ONNX (optimum[onnxruntime], Vietnamese) |
| Keywords | YAKE statistical + SpaCy NER |
| Dedup | MinHash LSH (datasketch) |
| Language detect | fasttext-wheel |
| BI analytics | Polars DataFrames |
| Compression | Zstandard |
| Logging | loguru (structured JSON) |
| Metrics | prometheus-client (no-op fallback) |
| Config | YAML + env (Viper-style priority) |
| Interfaces | `typing.Protocol` (runtime-checkable) |

---

## Security

- Do not commit `config.local.yaml` or any file containing credentials. Use environment variables or a secrets manager in production.
- Use a least-privilege database user (`analyst_prod`) for runtime; reserve `analyst_master` for migrations only.
- Restrict Kafka, PostgreSQL, Redis, and MinIO network access to trusted VPC/subnet.
- MinIO credentials must be provided via environment variables — they are intentionally absent from `config.yaml`.

---

## License

Part of SMAP graduation project (HCMUT). See [LICENSE](./LICENSE).

---

**Version**: 0.1.0 | **Python**: 3.12+ | **Tests**: 180 passed
