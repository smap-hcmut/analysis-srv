# Analytics Engine

A high-performance analytics processing service for social media content analysis, featuring **Vietnamese sentiment analysis** powered by PhoBERT ONNX.

---

## Key Features

### Core Capabilities

- **Vietnamese Sentiment Analysis** - 5-class sentiment prediction (1-5 stars) using PhoBERT
- **Intent Classification** - 7-category intent classifier with skip logic for spam filtering
- **Text Preprocessing** - Content merging, normalization, and noise detection
- **ONNX Optimization** - Quantized model for fast CPU inference (<100ms)
- **Clean Architecture** - Modular design with clear separation of concerns
- **Production-Ready** - Comprehensive testing, logging, and error handling
- **Database Integration** - PostgreSQL with Alembic migrations

### AI/ML Features

- **PhoBERT ONNX** - Fine-tuned Vietnamese BERT for sentiment analysis
- **Intent Classifier** - Regex-based intent detection (<0.01ms per prediction)
- **Text Preprocessing** - Vietnamese slang normalization and spam detection
- **SpaCy-YAKE** - Keyword extraction with NER and statistical methods
- **Text Segmentation** - PyVi integration for Vietnamese word segmentation
- **Batch Processing** - Efficient batch prediction support
- **Probability Distribution** - Confidence scores and full probability output
- **Model Management** - Download from MinIO, cached locally

### Performance

- **Fast Inference** - <100ms per prediction
- **Memory Efficient** - Model loaded once, reused for all requests
- **Scalable** - Stateless design, easy to horizontally scale
- **Optimized** - Quantized ONNX model for CPU deployment

### Event-Driven Integration

- **Crawler Integration** - Consumes `data.collected` events from Crawler services
- **Batch Processing** - Processes 20-50 items per batch efficiently
- **Error Handling** - Graceful error handling with categorization
- **Dual-Mode Support** - Supports both new event format and legacy messages

---

## Crawler Event Integration

The Analytics Engine integrates with Crawler services via RabbitMQ events.

### Event Schema

```json
{
  "event_id": "unique-event-id",
  "event_type": "data.collected",
  "timestamp": "2025-12-07T10:00:00Z",
  "payload": {
    "minio_path": "crawl-results/tiktok/2025/12/07/batch_001.json",
    "project_id": "proj_abc",
    "job_id": "proj_abc-brand-0",
    "batch_index": 0,
    "content_count": 50,
    "platform": "tiktok",
    "task_type": "research_and_crawl",
    "keyword": "vinfast"
  }
}
```

### Queue Configuration

| Setting     | Value                      |
| ----------- | -------------------------- |
| Exchange    | `smap.events`              |
| Routing Key | `data.collected`           |
| Queue Name  | `analytics.data.collected` |

### Batch Processing

- **TikTok**: 50 items per batch
- **YouTube**: 20 items per batch
- **Concurrent Batches**: Up to 5 (configurable)
- **Timeout**: 30 seconds per batch

### Error Handling

The service categorizes and stores crawler errors:

| Category      | Error Codes                                    |
| ------------- | ---------------------------------------------- |
| Rate Limiting | `RATE_LIMITED`, `AUTH_FAILED`, `ACCESS_DENIED` |
| Content       | `CONTENT_REMOVED`, `CONTENT_NOT_FOUND`         |
| Network       | `NETWORK_ERROR`, `TIMEOUT`, `DNS_ERROR`        |
| Parsing       | `PARSE_ERROR`, `INVALID_URL`                   |

### Configuration

```bash
# Event Queue Settings (Input)
EVENT_EXCHANGE=smap.events
EVENT_ROUTING_KEY=data.collected
EVENT_QUEUE_NAME=analytics.data.collected

# Result Publishing Settings (Output)
PUBLISH_EXCHANGE=results.inbound
PUBLISH_ROUTING_KEY=analyze.result
PUBLISH_ENABLED=true

# Batch Processing
MAX_CONCURRENT_BATCHES=5
BATCH_TIMEOUT_SECONDS=30
EXPECTED_BATCH_SIZE_TIKTOK=50
EXPECTED_BATCH_SIZE_YOUTUBE=20
```

### Result Publishing

After processing a batch, Analytics Engine publishes results back to Collector Service via RabbitMQ.

**Output Message Schema:**

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
        "topics": ["technology", "electric_vehicle"]
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

**Queue Configuration (Output):**

| Setting     | Value             |
| ----------- | ----------------- |
| Exchange    | `results.inbound` |
| Routing Key | `analyze.result`  |

### Documentation

- [Integration Contract](document/integration-contract.md) - Detailed requirements for Crawler services
- [Integration Analytics Service](document/integration-analytics-service.md) - Analytics ↔ Collector integration guide
- [Batch Processing Rationale](document/batch-processing-rationale.md) - Technical justification for batch processing architecture
- [Migration Guide](document/migration-guide.md) - Steps to migrate from legacy format
- [Rollback Runbook](document/rollback-runbook.md) - Emergency rollback procedures
- [Troubleshooting Guide](document/troubleshooting-guide.md) - Common issues and solutions

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **Docker & Docker Compose** (for containerized deployment)
- **PostgreSQL** (for database)
- **MinIO** (for model artifacts storage)

### 1. Clone Repository

```bash
git clone <repository-url>
cd analytics_engine
```

### 2. Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 4. Download PhoBERT Model

```bash
make download-phobert
# Follow prompts to enter MinIO credentials
```

### 5. Start Services

```bash
# Start development environment (Postgres, Redis, MinIO)
make dev-up

# Run database migrations
make db-upgrade

# Start API service
make run-api
```

### 6. Test the System

```bash
# Run all tests
make test

# Run API service tests
make test-api

# Run PhoBERT tests
make test-phobert

# Run unit tests only
make test-phobert-unit

# Run integration tests (requires model)
make test-phobert-integration
```

---

## API Service

The Analytics Engine includes a RESTful API service built with FastAPI that provides programmatic access to analytics data with comprehensive filtering, sorting, and pagination capabilities.

### Features

- **FastAPI Framework** with automatic OpenAPI documentation
- **Async Database Layer** with SQLAlchemy and connection pooling
- **Repository Pattern** with clean separation of concerns
- **Standardized Response Format** with success/error/pagination metadata
- **Comprehensive Filtering** for posts, trends, keywords, alerts, and errors
- **Performance Optimized** with database indexes and query optimization
- **Production Ready** with health checks, CORS, and error handling
- **Kubernetes Deployment** with ingress and security configurations

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Simple health check |
| `/health/detailed` | GET | Detailed health check with dependencies |
| `/posts` | GET | Get posts with filtering and pagination |
| `/posts/all` | GET | Get all posts without pagination |
| `/posts/{post_id}` | GET | Get specific post details |
| `/summary` | GET | Get analytics summary statistics |
| `/trends` | GET | Get trending topics and keywords |
| `/top-keywords` | GET | Get keyword analysis data |
| `/alerts` | GET | Get system alerts and notifications |
| `/errors` | GET | Get processing errors with details |

### Quick API Start

```bash
# Start API service
make run-api

# Or with Docker
make dev-up  # Includes API service

# Test the API
curl http://localhost:8000/health

# View documentation
open http://localhost:8000/swagger
```

### API Examples

```bash
# Get posts with filters
curl "http://localhost:8000/posts?platform=tiktok&sentiment=positive&limit=10"

# Get trending keywords
curl "http://localhost:8000/trends?period=7d&sort=engagement_desc"

# Get analytics summary
curl "http://localhost:8000/summary?project_id=proj_123"
```

### Environment Configuration

API-specific environment variables in `.env`:

```bash
# API Service
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
API_CORS_ORIGINS=http://localhost:3000,https://dashboard.yourdomain.com

# Database (Async)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/analytics
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Deployment

#### Docker Compose (Development)
```bash
make dev-up  # Starts all services including API
make dev-api-logs  # View API logs
```

#### Kubernetes (Production)
```bash
# Deploy all services
make k8s-deploy

# Check API status
make k8s-api-status

# View API logs
make k8s-logs-api
```

#### Docker Build

**Using build scripts (Recommended):**
```bash
# Build and push API service
./scripts/build-api.sh

# Build and push Consumer service
./scripts/build-consumer.sh

# Login to registry
./scripts/build-api.sh login
```

**Using Makefile:**
```bash
# Build API service image
make docker-build-api
```

### API Documentation

- **Swagger UI**: http://localhost:8000/swagger
- **ReDoc**: http://localhost:8000/redoc  
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Testing

```bash
# Run API tests
make test-api

# Run integration tests  
PYTHONPATH=. uv run pytest tests/integration/api/test_endpoints.py -v

# Test specific endpoints with curl
curl -X GET "http://localhost:8000/health"
curl -X GET "http://localhost:8000/posts?project_id=550e8400-e29b-41d4-a716-446655440000"
```

### Production Deployment Checklist

#### Pre-deployment
- [ ] Update `API_CORS_ORIGINS` to specific domains (remove `*`)
- [ ] Set `DEBUG=false` in production environment
- [ ] Configure proper `DATABASE_URL` with production credentials
- [ ] Set appropriate `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`
- [ ] Configure `LOG_LEVEL=INFO` or `WARNING` for production
- [ ] Verify SSL/TLS certificates for ingress

#### Kubernetes Deployment
- [ ] Apply namespace and RBAC configurations
- [ ] Deploy secrets with `kubectl apply -f k8s/api-service/deployment.yaml` (includes secrets)
- [ ] Deploy service with `kubectl apply -f k8s/api-service/service.yaml`
- [ ] Deploy configmap with `kubectl apply -f k8s/api-service/configmap.yaml`
- [ ] Merge ingress path into existing ingress (see `k8s/api-service/INGRESS_MERGE_GUIDE.md`)
- [ ] Verify pod health with `kubectl get pods -l app=analytics-api`
- [ ] Check logs with `kubectl logs -l app=analytics-api --tail=100`
- [ ] Test external access through ingress

#### Post-deployment Verification
- [ ] Health check: `curl https://smap-api.tantai.dev/analytics/health`
- [ ] API documentation: `curl https://smap-api.tantai.dev/analytics/openapi.json`
- [ ] Test endpoint: `curl https://smap-api.tantai.dev/analytics/posts?project_id=xxx`
- [ ] Database connectivity and performance
- [ ] Monitor resource usage (3 fixed replicas)
- [ ] Set up alerting for critical errors

---

## PhoBERT Integration

### Overview

The Analytics Engine uses **PhoBERT ONNX** for Vietnamese sentiment analysis, providing 5-class predictions (1-5 stars).

### Usage Example

```python
from infrastructure.ai import PhoBERTONNX

# Initialize model
model = PhoBERTONNX()

# Single prediction
result = model.predict("Sản phẩm chất lượng cao, rất hài lòng!")
print(result)
# {
#     'rating': 5,
#     'sentiment': 'VERY_POSITIVE',
#     'confidence': 0.95,
#     'probabilities': {
#         'VERY_NEGATIVE': 0.01,
#         'NEGATIVE': 0.01,
#         'NEUTRAL': 0.02,
#         'POSITIVE': 0.01,
#         'VERY_POSITIVE': 0.95
#     }
# }

# Batch prediction
texts = ["Text 1", "Text 2", "Text 3"]
results = model.predict_batch(texts)
```

### Model Specifications

| Property           | Value                        |
| ------------------ | ---------------------------- |
| **Model**          | PhoBERT (vinai/phobert-base) |
| **Task**           | 5-class sentiment analysis   |
| **Format**         | ONNX (quantized)             |
| **Size**           | ~150MB                       |
| **Inference Time** | <100ms                       |
| **Memory**         | ~200-300MB                   |

### Configuration

Constants can be customized in `infrastructure/ai/constants.py`:

```python
DEFAULT_MODEL_PATH = "infrastructure/phobert/models"
DEFAULT_MAX_LENGTH = 128
SENTIMENT_MAP = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
```

---

### 3. Text Preprocessing (New)

The `TextPreprocessor` module standardizes and cleans input text before AI processing.

**Features:**

- **Content Merging**: Combines Transcription > Caption > Top Comments
- **Normalization**: Unicode NFC, URL removal, Emoji removal, Hashtag handling
- **Noise Detection**: Calculates stats like hashtag ratio and length to filter spam

**Usage:**

```python
from services.analytics.preprocessing import TextPreprocessor

preprocessor = TextPreprocessor()
result = preprocessor.preprocess({
    "content": {
        "text": "Amazing product! 🔥 #review",
        "transcription": "Video transcript here..."
    },
    "comments": [{"text": "Great!", "likes": 5}]
})

print(result.clean_text)
# Output: "video transcript here... amazing product! review. great!"
```

---

### 4. Intent Classification (New)

The `IntentClassifier` module categorizes Vietnamese social media posts into 7 intent types using regex-based pattern matching, serving as a gatekeeper to filter noise before expensive AI processing.

**Features:**

- **7 Intent Categories**: CRISIS, SEEDING, SPAM, COMPLAINT, LEAD, SUPPORT, DISCUSSION
- **Priority Resolution**: Handles conflicting patterns with priority-based conflict resolution
- **Skip Logic**: Automatically marks SPAM/SEEDING posts for filtering before AI
- **Lightning Fast**: <0.01ms per prediction (100x faster than 1ms target)
- **Vietnamese Optimized**: Patterns designed for Vietnamese social media text

**Intent Categories:**

| Intent         | Priority | Description                    | Action          |
| -------------- | -------- | ------------------------------ | --------------- |
| **CRISIS**     | 10       | Brand crisis (scam, boycott)   | Alert + Process |
| **SEEDING**    | 9        | Spam marketing (phone numbers) | **SKIP**        |
| **SPAM**       | 9        | Garbage (loans, ads)           | **SKIP**        |
| **COMPLAINT**  | 7        | Product/service complaints     | Flag + Process  |
| **LEAD**       | 5        | Sales opportunities            | Flag + Process  |
| **SUPPORT**    | 4        | Technical support requests     | Flag + Process  |
| **DISCUSSION** | 1        | Normal discussion (default)    | Process         |

**Usage:**

```python
from services.analytics.intent import IntentClassifier

# Initialize classifier
classifier = IntentClassifier()

# Classify a post
result = classifier.predict("VinFast lừa đảo khách hàng, tẩy chay ngay!")

print(f"Intent: {result.intent.name}")  # CRISIS
print(f"Confidence: {result.confidence}")  # 0.80
print(f"Should Skip: {result.should_skip}")  # False
print(f"Matched Patterns: {result.matched_patterns}")

# Example: Filter spam before AI processing
if result.should_skip:
    print("⛔ SKIP - No AI processing needed")
else:
    print("✅ PROCESS - Send to sentiment analysis")
```

**Configuration:**

The classifier loads patterns from `config/intent_patterns.yaml` for easy customization without code changes. If the YAML file is missing or invalid, it falls back to hardcoded default patterns.

```yaml
# config/intent_patterns.yaml
CRISIS:
  - "tẩy\\s*chay"
  - "lừa\\s*đảo"
  - "scam"
  # Unsigned variations
  - "tay chay"
  - "lua dao"

SEEDING:
  - "\\b0\\d{9,10}\\b" # Phone numbers
  - "zalo.*\\d{9,10}"
  # Native ads detection
  - "trải\\s*nghiệm.*liên\\s*hệ.*\\d{9}"
# ... more patterns
```

Environment variables in `.env`:

```bash
INTENT_CLASSIFIER_ENABLED=true
INTENT_CLASSIFIER_CONFIDENCE_THRESHOLD=0.5
INTENT_PATTERNS_PATH=config/intent_patterns.yaml
```

**Performance:**

```
Single prediction: 0.015ms average (with YAML patterns)
Batch (100 posts): 185,687 posts/second
Memory: ~10KB (patterns only)
Pattern count: 75+ (vs 40 hardcoded defaults)
```

---

### 5. Impact & Risk Calculator (New)

The **ImpactCalculator** (Module 5) turns raw engagement, reach and sentiment into a
normalized **Impact Score (0–100)** and a discrete **Risk Level**.

**Inputs:**

- Interaction metrics: `views`, `likes`, `comments_count`, `shares`, `saves`
- Author metrics: `followers`, `is_verified`
- Overall sentiment: `{"label": "NEGATIVE|NEUTRAL|POSITIVE", "score": float}`
- Platform: `"TIKTOK" | "FACEBOOK" | "YOUTUBE" | "INSTAGRAM" | "UNKNOWN"`

**Core formula:**

- EngagementScore:
  \[
  E = views \cdot W*v + likes \cdot W_l + comments \cdot W_c + saves \cdot W_s + shares \cdot W*{sh}
  \]
- ReachScore:
  \[
  R = \log\_{10}(followers + 1) \times (1.2 \text{ if verified else } 1.0)
  \]
- Raw impact:
  \[
  RawImpact = E \cdot R \cdot M*{platform} \cdot M*{sentiment}
  \]
- Normalized ImpactScore:
  \[
  ImpactScore = \min\left(100,\ \max\left(0,\ \frac{RawImpact}{MAX_RAW_SCORE_CEILING} \cdot 100\right)\right)
  \]

**Risk levels:**

- `CRITICAL`: High impact (≥70), NEGATIVE, KOL (followers ≥ 50,000)
- `HIGH`: High impact (≥70), NEGATIVE, non‑KOL
- `MEDIUM`: Medium impact (≥40 & <70) with NEGATIVE, or high impact (≥60) with NEUTRAL/POSITIVE
- `LOW`: All other cases

**Usage:**

```python
from services.analytics.impact import ImpactCalculator

calc = ImpactCalculator()
result = calc.calculate(
    interaction={
        "views": 100_000,
        "likes": 5_000,
        "comments_count": 800,
        "shares": 300,
        "saves": 150,
    },
    author={"followers": 100_000, "is_verified": True},
    sentiment={"label": "NEGATIVE", "score": -0.9},
    platform="TIKTOK",
)

print(result["impact_score"], result["risk_level"], result["is_viral"], result["is_kol"])
print(result["impact_breakdown"])
```

For more details, see `documents/impact_risk_module.md`.

**Edge Cases Handled:**

- ✅ Native ads / Seeding trá hình (subtle marketing)
- ✅ Sarcasm / Complaint mỉa mai (sarcastic complaints)
- ✅ Unsigned Vietnamese (text without diacritics)
- ✅ Support vs Lead distinction

**Commands:**

```bash
# Run intent classifier tests
make test-intent  # 52 tests

# Run unit tests only
make test-intent-unit

# Run performance benchmarks
make test-intent-performance

# Run the example
make run-example-intent
```

---

### 5. SpaCy-YAKE Keyword Extraction

### Overview

The Analytics Engine uses **SpaCy + YAKE** for keyword extraction, combining linguistic analysis with statistical methods to identify important keywords and phrases.

### Usage Example

```python
from infrastructure.ai import SpacyYakeExtractor

# Initialize extractor
extractor = SpacyYakeExtractor()

# Extract keywords
text = "Machine learning is transforming data science and AI applications."
result = extractor.extract(text)

print(f"Keywords: {len(result.keywords)}")
print(f"Confidence: {result.confidence_score:.2f}")

for kw in result.keywords[:5]:
    print(f"  - {kw['keyword']} (score: {kw['score']:.2f}, type: {kw['type']})")

# Batch processing
texts = ["Text 1", "Text 2", "Text 3"]
results = extractor.extract_batch(texts)
```

### Model Specifications

| Property           | Value                                  |
| ------------------ | -------------------------------------- |
| **Method**         | SpaCy + YAKE                           |
| **Features**       | NER, Noun Chunks, Statistical Keywords |
| **Languages**      | English (extensible)                   |
| **Inference Time** | <500ms                                 |
| **Memory**         | ~200-400MB                             |

### Configuration

Environment variables in `.env`:

```bash
SPACY_MODEL=en_core_web_sm
YAKE_LANGUAGE=en
YAKE_N=2
MAX_KEYWORDS=30
ENTITY_WEIGHT=0.7
CHUNK_WEIGHT=0.5
```

### Commands

```bash
# Download SpaCy model
make download-spacy-model

# Run tests
make test-spacyyake              # All tests (78 total)
make test-spacyyake-unit         # Unit tests (58 tests)
make test-spacyyake-integration  # Integration tests (14 tests)
make test-spacyyake-performance  # Performance tests (6 tests)
```

---

### 6. Aspect-Based Sentiment Analyzer (ABSA)

The `SentimentAnalyzer` module implements **Aspect-Based Sentiment Analysis (ABSA)** on top of the existing PhoBERT ONNX wrapper.
It provides:

- **Overall sentiment** for the full post
- **Aspect-level sentiment** for each business aspect (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)

#### Features

- **Context Windowing**: Extracts a smart context window (±N characters) around each keyword, with boundary snapping to avoid cutting words.
- **Weighted Aggregation**: Aggregates multiple mentions of the same aspect using confidence-weighted average.
- **Graceful Degradation**: If aspect analysis fails, falls back to overall sentiment instead of crashing.
- **Configurable Thresholds**: POSITIVE / NEGATIVE thresholds can be tuned via environment variables.

#### Usage

```python
from infrastructure.ai.phobert_onnx import PhoBERTONNX
from services.analytics.sentiment import SentimentAnalyzer

# 1. Initialize PhoBERT ONNX model
phobert = PhoBERTONNX()

# 2. Initialize SentimentAnalyzer (ABSA)
analyzer = SentimentAnalyzer(phobert)

text = "Xe thiết kế rất đẹp nhưng giá quá cao, pin thì hơi yếu."
keywords = [
    {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")},
    {"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")},
    {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.find("pin")},
]

result = analyzer.analyze(text, keywords)

print("Overall:", result["overall"])
print("Aspects:")
for aspect, data in result["aspects"].items():
    print(f"  - {aspect}: {data}")
```

#### Configuration

ABSA configuration is defined in `infrastructure/ai/constants.py` and can be overridden via environment variables:

```python
# Context Windowing
DEFAULT_CONTEXT_WINDOW_SIZE = int(os.getenv("CONTEXT_WINDOW_SIZE", "60"))

# Sentiment Thresholds (3-class mapping)
THRESHOLD_POSITIVE = float(os.getenv("THRESHOLD_POSITIVE", "0.25"))
THRESHOLD_NEGATIVE = float(os.getenv("THRESHOLD_NEGATIVE", "-0.25"))

# Score Mapping (5-class rating → numeric score)
SCORE_MAP = {
    1: -1.0,  # VERY_NEGATIVE
    2: -0.5,  # NEGATIVE
    3: 0.0,   # NEUTRAL
    4: 0.5,   # POSITIVE
    5: 1.0,   # VERY_POSITIVE
}
```

Environment variables in `.env`:

```bash
# ABSA / Sentiment Analyzer
CONTEXT_WINDOW_SIZE=60          # characters around keyword
THRESHOLD_POSITIVE=0.25         # > 0.25 → POSITIVE
THRESHOLD_NEGATIVE=-0.25        # < -0.25 → NEGATIVE
```

#### Commands

```bash
# Run sentiment (ABSA) tests
uv run pytest tests/sentiment -q

# Run example script (requires PhoBERT model)
uv run python examples/sentiment_example.py
```

---

## Project Structure

```
analytics_engine/
├── command/                  # Entry points
│   ├── api/                  # API service entry point
│   │   └── main.py          # FastAPI application startup
│   └── consumer/             # Consumer service
├── core/                     # Core functionality
│   ├── config.py            # Configuration management
│   ├── database.py          # Async database manager
│   └── validation.py        # Environment validation
├── infrastructure/           # External integrations
│   ├── ai/                  # AI models
│   │   ├── phobert_onnx.py # PhoBERT wrapper
│   │   └── constants.py    # AI constants
│   └── phobert/
│       └── models/          # Model artifacts (gitignored)
├── internal/                 # Implementation layer
│   └── api/                 # API implementation
│       ├── main.py          # FastAPI app with middleware
│       └── routes/          # API route handlers
├── models/                   # Data models
│   └── schemas/             # Pydantic schemas
│       ├── base.py         # Base response schemas
│       ├── posts.py        # Posts API schemas
│       ├── trends.py       # Trends API schemas
│       ├── keywords.py     # Keywords API schemas
│       ├── alerts.py       # Alerts API schemas
│       └── errors.py       # Error handling schemas
├── repository/              # Data access layer
│   ├── base_repository.py  # Abstract repository interface
│   └── analytics_api_repository.py # API data repository
├── services/                # Business logic
├── tests/                   # Test suite
│   ├── api/                # API service tests
│   │   ├── test_endpoints.py # Endpoint tests
│   │   └── test_integration.py # Integration tests
│   └── phobert/            # PhoBERT tests
│       ├── test_unit.py    # 21 unit tests
│       ├── test_integration.py # 9 integration tests
│       └── test_performance.py # 6 performance tests
├── examples/                # Usage examples
│   └── api_client.py       # API client examples
├── k8s/                     # Kubernetes manifests
│   ├── api-service/        # API service K8s configs
│   │   ├── deployment.yaml # Deployment with 3 replicas
│   │   ├── service.yaml   # ClusterIP service
│   │   ├── configmap.yaml # Configuration
│   │   └── INGRESS_MERGE_GUIDE.md # Guide to merge into existing ingress
│   └── kustomization.yaml # Kustomize configuration
├── documents/               # Documentation
│   └── phobert_report.md  # Model report
├── scripts/                 # Utility scripts
│   ├── build-api.sh        # Build and push API image
│   ├── build-consumer.sh   # Build and push Consumer image
│   └── download_phobert_model.sh
├── migrations/              # Alembic migrations
├── docker-compose.dev.yml  # Development environment (includes API)
├── Dockerfile.api          # API service Docker image
├── Makefile                # Common commands (with API targets)
└── pyproject.toml          # Project dependencies
```

---

## Development Guide

### Available Commands

```bash
# Services
make run-api                 # Start API service locally
make run-consumer            # Start Consumer service locally

# Development Environment
make dev-up                  # Start dev services (Postgres, Redis, MinIO, API)
make dev-down                # Stop dev services
make dev-logs                # View all dev logs
make dev-api-logs            # View API service logs only

# Database
make db-upgrade              # Run migrations
make db-downgrade            # Rollback migration

# Testing
make test                    # Run all tests
make test-api                # Run API service tests
make test-phobert            # Run all PhoBERT tests (35 tests)
make test-phobert-unit       # Run unit tests (21 tests)
make test-phobert-integration # Run integration tests (9 tests)
make test-phobert-performance # Run performance tests (6 tests)

# AI Models
make download-phobert        # Download model from MinIO
make download-spacy-model    # Download SpaCy model

# Docker
make docker-build           # Build consumer service image
make docker-build-api       # Build API service image

# Kubernetes
make k8s-deploy             # Deploy all services to Kubernetes
make k8s-delete             # Delete all Kubernetes resources
make k8s-logs-api           # View API service logs
make k8s-api-status         # Check API service status

# Code Quality
make format                 # Format code with Black
make lint                   # Lint code with flake8
make clean                  # Clean up cache files
```

### Running Tests

```bash
# All PhoBERT tests
make test-phobert

# Unit tests only (no model required)
make test-phobert-unit

# Integration tests (requires model)
make test-phobert-integration

# Performance benchmarks
make test-phobert-performance
```

### Test Coverage

- **Unit Tests**: 21/21 passing (100%)
- **Integration Tests**: 9/9 passing (100%)
- **Performance Tests**: 5/6 passing (1 skipped)
- **Total**: 35/35 tests passing

See [`documents/phobert_report.md`](documents/phobert_report.md) for detailed test results and benchmarks.

---

## Configuration

### Environment Variables

```bash
# Application
APP_NAME="Analytics Engine"
APP_VERSION="0.1.0"
ENVIRONMENT="development"

# API Service
API_HOST="0.0.0.0"
API_PORT=8000

# Database
DATABASE_URL="postgresql://user:pass@localhost:5432/analytics"

# PhoBERT Model
PHOBERT_MODEL_PATH="infrastructure/phobert/models"
PHOBERT_MAX_LENGTH=128

# MinIO (for model download)
MINIO_ENDPOINT="http://your-minio:9000"
MINIO_ACCESS_KEY="your-access-key"
MINIO_SECRET_KEY="your-secret-key"
```

---

## Architecture

### Clean Architecture Layers

```
┌─────────────────────────────────────┐
│  Entry Points (command/)           │
│  - API Service                      │
│  - Consumer Service                 │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Internal (internal/)               │
│  - API Routes                       │
│  - Schemas                          │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Services (services/)               │
│  - Business Logic                   │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  Infrastructure (infrastructure/)   │
│  - AI Models (PhoBERT)              │
│  - Database                         │
│  - External Services                │
└─────────────────────────────────────┘
```

---

## Documentation

- **Model Report**: [`documents/phobert_report.md`](documents/phobert_report.md)
- **Architecture**: [`documents/architecture.md`](documents/architecture.md)
- **OpenSpec Changes**: [`openspec/changes/archive/`](openspec/changes/archive/)

---

## Contact

- **Email**: nguyentantai.dev@gmail.com
- **Repository**: [GitHub](https://github.com/nguyentantai21042004/analytics_engine)

---

## Test API Endpoint

The Analytics Engine provides a `/test/analytics` endpoint for testing the full analytics pipeline integration.

### Sentiment & ABSA (Module 4)

The analytics engine uses a Vietnamese sentiment model based on
`wonrax/phobert-base-vietnamese-sentiment` (3-class: NEG/NEU/POS) and maps
its outputs into a 1–5★ business rating scale:

- NEGATIVE (index 0) → **1★** (Very Negative)
- NEUTRAL (index 2) → **3★** (Neutral)
- POSITIVE (index 1) → **5★** (Very Positive)

On top of this overall sentiment, the `SentimentAnalyzer` implements
Aspect-Based Sentiment Analysis (ABSA):

- Uses **context windowing** around each keyword (CONFIG: `CONTEXT_WINDOW_SIZE`,
  default 30 characters) to avoid “sentiment bleeding” between clauses.
- Cuts windows on punctuation and Vietnamese pivot words (`nhưng`, `tuy nhiên`,
  `mặc dù`, `bù lại`) so that:
  - DESIGN praise (e.g. _"Xe thiết kế rất đẹp"_) is evaluated separately.
  - PRICE complaints (e.g. _"giá quá cao"_) are not diluted by positive parts.
  - PERFORMANCE issues (e.g. _"pin thì hơi yếu"_) are localized.
- Returns both:
  - **overall** sentiment (label, score in [-1,1], rating 1–5★, confidence).
  - **aspects** dictionary keyed by business aspect (`DESIGN`, `PRICE`,
    `PERFORMANCE`, `SERVICE`, …) with per-aspect label/score/rating and mentions.

Model files are downloaded from MinIO via:

- `make download-phobert` → runs `scripts/download_phobert_model.py` using:
  - `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
  - Downloads: `model_quantized.onnx`, `config.json`, `vocab.txt`,
    `special_tokens_map.json`, `tokenizer_config.json`,
    `added_tokens.json`, `bpe.codes` into `infrastructure/phobert/models/`.

### Endpoint Details

**URL**: `POST /test/analytics`  
**Description**: Test endpoint that accepts JSON input matching the master-proposal format and returns detailed analytics processing results.

### Request Format

```json
{
  "meta": {
    "id": "post_123",
    "platform": "facebook",
    "lang": "vi",
    "collected_at": "2025-01-15T10:30:00Z"
  },
  "content": {
    "title": "Đánh giá sản phẩm",
    "text": "Sản phẩm chất lượng cao, rất hài lòng!",
    "media": []
  },
  "interaction": {
    "likes": 42,
    "shares": 5,
    "comments_count": 3
  },
  "author": {
    "id": "user_456",
    "name": "John Doe"
  },
  "comments": []
}
```

### Response Format

```json
{
  "post_id": "post_123",
  "preprocessing": {
    "status": "not_implemented",
    "message": "Text preprocessing will be implemented in a future proposal",
    "input_text_length": 54
  },
  "keywords": {
    "status": "success",
    "model_available": true,
    "keywords": [
      {
        "keyword": "sản phẩm",
        "score": 0.95,
        "rank": 1,
        "type": "statistical"
      }
    ],
    "metadata": {
      "extraction_time": 0.123,
      "total_candidates": 15
    }
  },
  "sentiment": {
    "status": "success",
    "model_available": true,
    "sentiment": {
      "sentiment": "VERY_POSITIVE",
      "confidence": 0.99,
      "probabilities": {
        "VERY_NEGATIVE": 0.001,
        "NEGATIVE": 0.002,
        "NEUTRAL": 0.007,
        "POSITIVE": 0.01,
        "VERY_POSITIVE": 0.98
      }
    }
  },
  "metadata": {
    "platform": "facebook",
    "language": "vi",
    "collected_at": "2025-01-15T10:30:00Z",
    "models_initialized": {
      "phobert": true,
      "spacyyake": true
    }
  }
}
```

### Testing with curl

```bash
# Test with Vietnamese text
curl -X POST http://localhost:8000/test/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "meta": {"id": "test_1", "platform": "facebook", "lang": "vi"},
    "content": {"title": "Review", "text": "Sản phẩm tốt!"},
    "interaction": {},
    "author": {},
    "comments": []
  }'

# Test with English text
curl -X POST http://localhost:8000/test/analytics \
  -H "Content-Type: application/json" \
  -d '{
    "meta": {"id": "test_2", "platform": "twitter", "lang": "en"},
    "content": {"title": "Product Review", "text": "Great quality product with excellent features!"},
    "interaction": {},
    "author": {},
    "comments": []
  }'
```

### Testing with Python

```python
import requests

# Prepare test data
test_data = {
    "meta": {
        "id": "test_post_123",
        "platform": "facebook",
        "lang": "vi",
        "collected_at": "2025-01-15T10:30:00Z"
    },
    "content": {
        "title": "Đánh giá sản phẩm",
        "text": "Sản phẩm chất lượng cao, rất hài lòng!",
        "media": []
    },
    "interaction": {"likes": 42, "shares": 5, "comments_count": 3},
    "author": {"id": "user_456", "name": "John Doe"},
    "comments": []
}

# Send request
response = requests.post(
    "http://localhost:8000/test/analytics",
    json=test_data
)

# Process response
result = response.json()
print(f"Post ID: {result['post_id']}")
print(f"Sentiment: {result['sentiment']['sentiment']['sentiment']}")
print(f"Keywords: {len(result['keywords']['keywords'])} extracted")
```

### API Documentation

Once the API is running, visit:

- **Swagger UI**: http://localhost:8000/swagger or http://localhost:8000/swagger/index.html
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

---

## MinIO Compression

The Analytics Engine supports **Zstd compression** for MinIO storage, providing automatic decompression when downloading JSON files.

### Features

- **Zstd Algorithm**: High compression ratio (60-95% for JSON) with fast decompression
- **Auto-Detection**: Automatically detects compressed files via metadata
- **Backward Compatible**: Uncompressed files continue to work without changes
- **Configurable**: Compression level and settings can be customized

### Configuration

Environment variables in `.env`:

```bash
# Compression Settings
COMPRESSION_ENABLED=true           # Enable/disable compression
COMPRESSION_DEFAULT_LEVEL=2        # Compression level (0-3)
COMPRESSION_ALGORITHM=zstd         # Compression algorithm
COMPRESSION_MIN_SIZE_BYTES=1024    # Minimum size to compress
```

### Compression Levels

| Level | Description            | Compression Ratio | Speed    |
| ----- | ---------------------- | ----------------- | -------- |
| 0     | No compression         | 0%                | Fastest  |
| 1     | Fast compression       | ~50-70%           | Fast     |
| **2** | **Balanced (default)** | **~70-85%**       | **Good** |
| 3     | Best compression       | ~85-95%           | Slower   |

### Usage

The `MinioAdapter` automatically handles compression/decompression:

```python
from infrastructure.storage.minio_client import MinioAdapter

# Initialize adapter
adapter = MinioAdapter()

# Download JSON - auto-decompresses if compressed
data = adapter.download_json("bucket-name", "path/to/file.json")

# Compression methods (for advanced usage)
compressed = adapter._compress_data(b"raw data", level=2)
decompressed = adapter._decompress_data(compressed)

# Check if file is compressed
is_compressed = adapter._is_compressed(metadata)

# Build metadata for upload
metadata = adapter._build_compression_metadata(
    original_size=1000,
    compressed_size=500,
    level=2
)
```

### Metadata Structure

Compression metadata is stored in MinIO object headers:

| Header                             | Description                         |
| ---------------------------------- | ----------------------------------- |
| `x-amz-meta-compression-algorithm` | Algorithm used (e.g., "zstd")       |
| `x-amz-meta-compression-level`     | Compression level (0-3)             |
| `x-amz-meta-original-size`         | Original uncompressed size in bytes |
| `x-amz-meta-compressed-size`       | Compressed size in bytes            |

### Testing

```bash
# Run compression tests
uv run pytest tests/storage/test_compression.py -v

# Run integration tests
uv run pytest tests/storage/test_integration.py -v

# Run all storage tests
uv run pytest tests/storage/ -v
```

---
