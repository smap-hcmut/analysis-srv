# Architecture Documentation - Analytics Engine

## Overview

This document describes the project structure and architectural patterns used in the Analytics Engine service. This structure can be replicated across other repository for consistency.

## Directory Structure

```
analytics_engine/
├── command/                   # Entry Points (Command Layer)
│   ├── api/                    # API service entry point
│   │   ├── __init__.py
│   │   └── main.py            # Loads config, initializes FastAPI app
│   └── consumer/               # Consumer service entry point
│       ├── __init__.py
│       └── main.py            # Loads config, initializes instances, starts consumer
│
├── internal/                   # Internal Implementation Layer
│   ├── api/                    # API route registration
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app, middleware, exception handlers
│   │   └── routes/            # API route modules
│   │       ├── __init__.py
│   │       ├── posts.py       # /posts endpoints
│   │       ├── summary.py     # /summary endpoint
│   │       ├── trends.py      # /trends endpoint
│   │       ├── keywords.py    # /top-keywords endpoint
│   │       ├── alerts.py      # /alerts endpoint
│   │       └── errors.py      # /errors endpoint
│   └── consumers/              # Consumer registration
│       ├── __init__.py
│       └── main.py            # Event consumer (data.collected events)
│
├── core/                       # Core Shared Layer
│   ├── __init__.py
│   ├── config.py              # Application settings (Pydantic Settings)
│   ├── logger.py              # Logging configuration (Loguru)
│   ├── constants.py           # Error codes, categories, enums
│   ├── dependencies.py        # Dependency injection
│   └── errors.py              # Custom exceptions
│
├── models/                     # Data Models Layer
│   ├── __init__.py
│   ├── database.py            # SQLAlchemy models (PostAnalytics, CrawlError)
│   ├── schemas/               # Pydantic schemas (API DTOs)
│   │   ├── __init__.py
│   │   ├── base.py            # Base schemas, response wrappers
│   │   ├── posts.py           # Post request/response schemas
│   │   ├── summary.py         # Summary response schemas
│   │   ├── trends.py          # Trends response schemas
│   │   └── errors.py          # Error response schemas
│   └── messages.py            # RabbitMQ message schemas
│
├── interfaces/                 # Interface Layer (Abstractions)
│   ├── __init__.py
│   ├── repository.py          # Abstract repository interface
│   ├── storage.py             # Abstract storage interface (MinIO)
│   └── queue.py               # Abstract message queue interface
│
├── repository/               # Repository Implementations
│   ├── __init__.py
│   ├── analytics_repository.py # PostAnalytics repository
│   └── crawl_error_repository.py # CrawlError repository
│
├── services/                   # Business Logic Layer
│   └── analytics/
│       ├── orchestrator.py    # Central analytics pipeline coordinator
│       ├── preprocessor.py    # Text preprocessing
│       ├── intent.py          # Intent classification
│       ├── keyword.py         # Keyword extraction
│       ├── sentiment.py       # Sentiment analysis
│       └── impact.py          # Impact calculation
│
├── infrastructure/             # Infrastructure Implementations
│   ├── storage/               # Storage implementations
│   │   ├── minio_client.py    # MinIO adapter (download_json, download_batch)
│   │   └── constants.py       # Storage constants
│   ├── messaging/             # Message queue implementations
│   │   └── rabbitmq.py        # RabbitMQ connection and binding
│   └── ai/                    # AI model implementations
│       └── phobert.py         # PhoBERT ONNX model
│
├── utils/                      # Utility Functions
│   └── project_id_extractor.py # Extract project_id from job_id
│
├── migrations/                 # Database Migrations (Alembic)
│   ├── versions/
│   └── env.py                 # Alembic environment configuration
│
├── config/                     # Configuration Files
│   ├── archive/               # Archived configurations
│   │   └── legacy_queue_config.yaml
│   └── canary_deployment.yaml # Canary deployment config
│
├── document/                   # Documentation
│   ├── analytics-service-behavior.md
│   ├── analytics-service-integration-guide.md
│   ├── architecture.md        # This file
│   └── ...
│
├── scripts/                    # Utility Scripts
│   ├── backup_database.sh
│   └── validate_migration.py
│
├── tests/                      # Test Suite
│   ├── unit/
│   ├── integration/
│   └── performance/
│
├── openspec/                   # OpenSpec specifications
├── pyproject.toml             # Python project configuration (uv)
├── docker-compose.dev.yml     # Development environment
├── Makefile                   # Common command
└── README.md
```

## Architectural Layers

### 1. Command Layer (`cmd/`)

**Purpose**: Entry points for services. Each service has its own directory.

**Responsibilities**:

- Load application configuration from `core.config`
- Initialize logging from `core.logger`
- Bootstrap dependency injection container (if applicable)
- Import and start the internal implementation
- Handle process lifecycle (startup, shutdown)

**Pattern**:

```python
# command/consumer/main.py
from core.config import settings
from core.logger import logger
from internal.consumers.main import create_message_handler

def main():
    # Load config, initialize instances
    logger.info(f"Starting {settings.service_name}")
    # Start consumer with message handler
    ...

if __name__ == "__main__":
    main()
```

**Key Points**:

- One entry point per service (Consumer, Worker, etc.)
- Minimal logic - just wiring and initialization
- Uses `internal/` for actual implementation

### 2. Internal Layer (`internal/`)

**Purpose**: Internal implementation of services. Registers routes, consumers, and handlers.

**Responsibilities**:

- Register API routes (FastAPI routers)
- Register message queue consumers
- Define middleware and exception handlers
- Implement service-specific logic

**Pattern - API**:

```python
# internal/api/main.py
from fastapi import FastAPI
from internal.api.routes import posts, summary, trends

app = FastAPI(title="Analytics Engine API")

# Register routes
app.include_router(posts.router, prefix="/v1/analytics", tags=["posts"])
app.include_router(summary.router, prefix="/v1/analytics", tags=["summary"])
app.include_router(trends.router, prefix="/v1/analytics", tags=["trends"])

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Pattern - Consumer**:

```python
# internal/consumers/main.py
from aio_pika import IncomingMessage

def create_message_handler(phobert, spacyyake):
    async def message_handler(message: IncomingMessage):
        # Process incoming message
        ...
    return message_handler
```

**Key Points**:

- Contains the actual service implementation
- Separated by service type (api, consumers, workers)
- Does NOT handle initialization - that's `command/`'s job

### 3. Core Layer (`core/`)

**Purpose**: Shared core functionality used across all services.

**Components**:

#### `config.py` - Application Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_name: str = "analytics-engine"
    database_url: str = "postgresql://..."
    # ...

settings = Settings()

def get_settings() -> Settings:
    return settings
```

#### `logger.py` - Logging Configuration

```python
from loguru import logger

def setup_logger():
    # Configure loguru handlers
    pass

setup_logger()
```

**Key Points**:

- Shared across all services
- No service-specific logic
- Provides common utilities and configurations
- Does NOT contain models (moved to `models/` layer)

### 4. Models Layer (`models/`)

**Purpose**: Data models and schemas.

**Components**:

#### `database.py` - SQLAlchemy Models

```python
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    id = Column(String(50), primary_key=True)
    # ...
```

#### `schemas.py` - Pydantic Schemas (Future)

```python
from pydantic import BaseModel

class PostAnalyticsCreate(BaseModel):
    project_id: str
    platform: str
    # ...
```

**Key Points**:

- Centralized location for all data models
- Separate database models from API schemas
- Easy to import: `from models.database import PostAnalytics`

### 5. Interfaces Layer (`interfaces/`)

**Purpose**: Abstract base classes for dependency injection.

**Responsibilities**:

- Define contracts for repository
- Define contracts for external services (storage, queue, cache)
- Enable dependency injection and testing

**Pattern**:

```python
# interfaces/repository.py
from abc import ABC, abstractmethod

class IAnalyticsRepository(ABC):
    @abstractmethod
    async def create(self, analytics: PostAnalytics) -> PostAnalytics:
        pass

    @abstractmethod
    async def get_by_id(self, analytics_id: str) -> Optional[PostAnalytics]:
        pass
```

**Key Points**:

- All interfaces use ABC (Abstract Base Class)
- Enables easy mocking for tests
- Decouples business logic from infrastructure

### 6. Repository Layer (`repository/`)

**Purpose**: Implement data access patterns.

**Responsibilities**:

- Implement `IAnalyticsRepository` interface
- Handle database operations
- Use SQLAlchemy for queries

**Pattern** (Future):

```python
# repository/analytics_repository.py
from interfaces.repository import IAnalyticsRepository
from models.database import PostAnalytics

class AnalyticsRepository(IAnalyticsRepository):
    def __init__(self, db_session):
        self.db = db_session

    async def create(self, analytics: PostAnalytics) -> PostAnalytics:
        self.db.add(analytics)
        await self.db.commit()
        return analytics
```

**Key Points**:

- Implements interfaces from `interfaces/`
- Handles all database operations
- Can be easily swapped for testing

### 7. Services Layer (`services/`)

**Purpose**: Business logic and domain services.

**Responsibilities**:

- Implement business logic
- Orchestrate operations
- Use dependency injection for infrastructure

**Pattern** (Future):

```python
# services/analytics_service.py
class AnalyticsService:
    def __init__(self, storage, database):
        self.storage = storage
        self.database = database

    def process_post(self, post_id):
        # Business logic here
        pass
```

#### 7.1 Analytics Orchestrator (`services/analytics/orchestrator.py`)

**Role**: Central coordinator for the full analytics pipeline.

**Pipeline**:

- Input: A single Atomic JSON post (`meta`, `content`, `interaction`, `author`, `comments`), enriched with batch context from crawler events.
- Steps:
  1. **Preprocessing** (`TextPreprocessor`):
     - Merge caption, transcription, and top comments.
     - Normalize Vietnamese text and compute noise stats (spam, too short, etc.).
  2. **Intent** (`IntentClassifier`):
     - Classify post intent and produce a `should_skip` signal.
  3. **Skip Logic**:
     - Combines preprocessor stats + intent to decide whether to skip spam/noise/seeding posts.
     - Skipped posts still persist a minimal `PostAnalytics` record with neutral sentiment and low risk.
  4. **Keyword Extraction** (`KeywordExtractor`):
     - Hybrid dictionary + SpaCy-YAKE extraction with aspect mapping.
  5. **Sentiment** (`SentimentAnalyzer`):
     - Overall + aspect-based sentiment using PhoBERT with smart context windowing.
  6. **Impact & Risk** (`ImpactCalculator`):
     - Compute engagement, reach, impact score (0–100), and risk level (LOW→CRITICAL).
  7. **Persistence** (`AnalyticsRepository`):
     - Save final `PostAnalytics` payload (overall, aspects, keywords, impact, raw metrics).
     - Includes batch context: `job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version`.

**Entry Point**:

- **Event Consumer** (`internal/consumers/main.py`):
  - Consumes `data.collected` events from `smap.events` exchange.
  - Event contains `payload.minio_path` pointing to batch file in MinIO.
  - Uses `MinioAdapter.download_batch()` to fetch batch of 20-50 items.
  - Extracts `project_id` from `job_id` using `utils/project_id_extractor.py`.
  - Processes each item independently:
    - Success items (`fetch_status: "success"`) → `AnalyticsOrchestrator.process_post()`
    - Error items (`fetch_status: "error"`) → `CrawlErrorRepository.save()`
  - Acknowledges message after batch completion.

**Event-Driven Flow**:

```text
Crawler Services (TikTok/YouTube)
    │
    ├─▶ Upload batch to MinIO (crawl-results bucket)
    └─▶ Publish data.collected event to smap.events exchange
                │
                ▼
RabbitMQ (analytics.data.collected queue)
                │
                ▼
internal/consumers/main.py
    │
    ├─▶ Parse event metadata (event_id, job_id, minio_path)
    ├─▶ MinioAdapter.download_batch() ──▶ MinIO (crawl-results)
    ├─▶ extract_project_id(job_id)
    │
    └─▶ For each item in batch:
            │
            ├─▶ [Success] AnalyticsOrchestrator.process_post()
            │                   └─▶ AnalyticsRepository.save() ──▶ PostgreSQL (post_analytics)
            │
            └─▶ [Error] CrawlErrorRepository.save() ──▶ PostgreSQL (crawl_errors)
```

### 5. Migrations Layer (`migrations/`)

**Purpose**: Database schema versioning with Alembic.

**Configuration**:

```python
# migrations/env.py
from core.models import Base
from core.config import settings

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url_sync)
```

## Dependency Flow

**API Service:**

```
command/api/main.py
    ↓ imports
internal/api/main.py
    ↓ uses
internal/api/routes/*.py
    ↓ uses
repository/ (data access)
    ↓ uses
models/database.py, models/schemas/
```

**Consumer Service:**

```
command/consumer/main.py
    ↓ imports
internal/consumers/main.py
    ↓ uses
core/config.py, core/logger.py
    ↓ uses
services/ (business logic)
```

## Key Principles

### 1. Separation of Concerns

- **command/**: Process management and initialization
- **internal/**: Service implementation
- **core/**: Shared utilities
- **services/**: Business logic

### 2. Dependency Injection

- Configuration loaded once in `command/`
- Passed down to `internal/` and `services/`
- No global state in business logic

### 3. Testability

- `internal/` and `services/` can be tested independently
- Mock `core/` components for unit tests
- Integration tests use `command/` entry points

### 4. Scalability

- Easy to add new services (new `command/` entry point)
- Easy to add new routes (register in `internal/api/routes/`)
- Easy to add new consumers (register in `internal/consumers/`)

## Configuration Management

### Environment Variables

Managed via `.env` file and `core/config.py`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Settings Class

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # Ignore extra fields
    )

    database_url: str
    service_name: str = "analytics-engine"
    # ...
```

## Development Workflow

### 1. Start Development Environment

```bash
make dev-up  # Starts Docker services
```

### 2. Run Services

```bash
make run-api       # Start API service
make run-consumer  # Start consumer service
```

### 3. Database Migrations

```bash
make db-migrate  # Create migration
make db-upgrade  # Apply migrations
```

## Adding a New Service

### Step 1: Create Entry Point

```bash
mkdir -p cmd/new_service
touch cmd/new_service/__init__.py
touch cmd/new_service/main.py
```

### Step 2: Create Internal Implementation

```bash
mkdir -p internal/new_service
touch internal/new_service/__init__.py
touch internal/new_service/main.py
```

### Step 3: Implement Entry Point

```python
# cmd/new_service/main.py
from core.config import settings
from core.logger import logger
from internal.new_service.main import run_service

if __name__ == "__main__":
    logger.info(f"Starting {settings.service_name}")
    run_service()
```

### Step 4: Implement Service Logic

```python
# internal/new_service/main.py
def run_service():
    # Service implementation
    pass
```

### Step 5: Add Makefile Command

```makefile
run-new-service:
	PYTHONPATH=. uv run cmd/new_service/main.py
```

## Technology Stack

- **Language**: Python 3.10+
- **Package Manager**: `uv`
- **Web Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Logging**: Loguru
- **Configuration**: Pydantic Settings
- **Message Queue**: RabbitMQ (aio-pika)
- **Storage**: MinIO (boto3-compatible)
- **Compression**: Zstandard (zstd)
- **AI/ML**: PhoBERT (ONNX), SpaCy-YAKE

## API Service Architecture

### Overview

Analytics API Service cung cấp REST API để query dữ liệu phân tích cho Dashboard.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Dashboard    │────▶│   Analytics     │────▶│   PostgreSQL    │
│    (Frontend)   │     │   API Service   │     │  post_analytics │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Entry Point

```python
# command/api/main.py
from core.config import settings
from core.logger import logger
from internal.api.main import app

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Analytics API on {settings.api_host}:{settings.api_port}")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
```

### API Endpoints

| Endpoint                     | Method | Description                              |
| ---------------------------- | ------ | ----------------------------------- |
| `/v1/analytics/posts`        | GET    | List posts với filters + pagination |
| `/v1/analytics/posts/{id}`   | GET    | Chi tiết 1 post + comments          |
| `/v1/analytics/summary`      | GET    | Thống kê tổng hợp                   |
| `/v1/analytics/trends`       | GET    | Data theo timeline                  |
| `/v1/analytics/top-keywords` | GET    | Top keywords với sentiment          |
| `/v1/analytics/alerts`       | GET    | Posts cần chú ý                     |
| `/v1/analytics/errors`       | GET    | Crawl errors tracking               |
| `/health`                    | GET    | Health check                        |
| `/swagger/index.html`        | GET    | Swagger UI documentation            |
| `/openapi.json`              | GET    | OpenAPI 3.0 specification           |

### Response Format

All responses follow standard format:

**Success:**

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

**Paginated:**

```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  },
  "meta": { ... }
}
```

**Error:**

```json
{
  "success": false,
  "error": {
    "code": "VAL_001",
    "message": "Validation failed",
    "details": [...]
  },
  "meta": { ... }
}
```

### Filter Parameters

All endpoints support filtering by:

- `project_id` (UUID) - **Required**
- `brand_name` (string) - Optional
- `keyword` (string) - Optional

---

## Event-Driven Architecture

### Overview

Analytics Service sử dụng event-driven architecture để consume data từ Crawler services:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Crawler        │     │   RabbitMQ      │     │   Analytics     │
│  Services       │────▶│   smap.events   │────▶│   Service       │
│  (TikTok/YT)    │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        ▼                                               ▼
┌─────────────────┐                           ┌─────────────────┐
│     MinIO       │◀──────────────────────────│   PostgreSQL    │
│  crawl-results  │                           │  post_analytics │
└─────────────────┘                           └─────────────────┘
```

### Event Schema

```json
{
  "event_id": "evt_abc123",
  "event_type": "data.collected",
  "timestamp": "2025-12-06T10:15:30Z",
  "payload": {
    "minio_path": "crawl-results/tiktok/proj_xyz/brand/batch_000.json",
    "project_id": "proj_xyz",
    "job_id": "proj_xyz-brand-0",
    "batch_index": 1,
    "content_count": 50,
    "platform": "tiktok"
  }
}
```

### Queue Configuration

| Setting        | Value                      |
| -------------- | -------------------------- |
| Exchange       | `smap.events`              |
| Exchange Type  | `topic`                    |
| Routing Key    | `data.collected`           |
| Queue Name     | `analytics.data.collected` |
| Prefetch Count | `1`                        |

### Batch Processing

- **TikTok**: 50 items per batch
- **YouTube**: 20 items per batch
- **Processing**: Per-item with independent error handling
- **Throughput**: ~1000 items/min (TikTok), ~300 items/min (YouTube)

### Error Handling

Error items (`fetch_status: "error"`) are stored in `crawl_errors` table with:

- 17 error codes across 7 categories
- Error categorization for monitoring
- Per-item failures don't crash batch

See `document/analytics-service-behavior.md` for detailed behavior specification.

## Best Practices

### 1. Import Organization

```python
# Standard library
import os
import sys

# Third-party
from aio_pika import IncomingMessage
from sqlalchemy import Column

# Local - core
from core.config import settings
from core.logger import logger

# Local - internal
from internal.consumers.main import create_message_handler

# Local - services
from services.analytics.orchestrator import AnalyticsOrchestrator
```

### 2. Error Handling

- Use custom exceptions from `core/errors.py`
- Log errors with context using `core/logger.py`
- Return consistent error responses

### 3. Configuration

- All configuration in `core/config.py`
- Use environment variables
- Provide sensible defaults
- Validate settings on startup

### 4. Logging

- Use structured logging
- Include context (service, function, line)
- Different log levels for different environments
- Separate error logs

## Replication Guide

To replicate this structure in a new repository:

1. **Copy Structure**:

   ```bash
   mkdir -p cmd/service_name internal/service_name core services migrations
   ```

2. **Copy Core Files**:

   - `core/config.py` (adapt settings)
   - `core/logger.py` (reuse as-is)
   - `core/models.py` (define your models)

3. **Create Entry Point**:

   - `cmd/service_name/main.py` (follow pattern above)

4. **Create Internal Implementation**:

   - `internal/service_name/main.py` (implement your service)

5. **Setup Dependencies**:

   - Copy `pyproject.toml` structure
   - Run `uv sync`

6. **Setup Database**:

   - Copy `migrations/env.py` pattern
   - Run `alembic init migrations`

7. **Setup Development Environment**:
   - Copy `docker-compose.dev.yml`
   - Copy `Makefile` patterns

This architecture ensures consistency, maintainability, and scalability across all services.
