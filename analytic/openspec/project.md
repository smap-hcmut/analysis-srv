# Project Context

## Purpose

**Analytics Engine** - Hệ thống xử lý phân tích nội dung mạng xã hội hiệu suất cao, chuyên biệt cho tiếng Việt. Hệ thống cung cấp pipeline phân tích hoàn chỉnh từ tiền xử lý văn bản đến tính toán mức độ ảnh hưởng và rủi ro.

## Tech Stack

### Core

- **Language**: Python 3.12+ (minimum 3.10)
- **Package Manager**: `uv` (faster than Poetry)
- **Web Framework**: FastAPI
- **Database**: PostgreSQL với Alembic migrations
- **Message Queue**: RabbitMQ (aio-pika)
- **Object Storage**: MinIO (model artifacts, compressed với Zstd)

### AI/ML Stack

- **PhoBERT ONNX** - Vietnamese sentiment analysis (3-class: NEG/NEU/POS → mapped to 1-5★)
- **SpaCy + YAKE** - Hybrid keyword extraction (NER + statistical)
- **PyVi** - Vietnamese text segmentation
- **ONNX Runtime** - Optimized CPU inference (<100ms)
- **Transformers** - Tokenization (AutoTokenizer)

### Infrastructure

- **Docker Compose** - Development & production environments
- **Compression**: Zstd (60-95% ratio for JSON)
- **Logging**: Loguru

## Architecture Overview

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Entry Points (command/)                                    │
│  └── consumer/main.py → RabbitMQ consumer (Event-Driven)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Internal (internal/)                                        │
│  └── consumers/       → Message handlers                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Services (services/analytics/)                              │
│  ├── orchestrator.py  → Pipeline coordinator                │
│  ├── preprocessing/   → Text normalization                  │
│  ├── intent/          → Intent classification               │
│  ├── keyword/         → Hybrid keyword extraction           │
│  ├── sentiment/       → ABSA sentiment analysis             │
│  └── impact/          → Impact & risk calculation           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure (infrastructure/)                            │
│  ├── ai/              → AI models (PhoBERT, SpaCy-YAKE)     │
│  ├── messaging/       → RabbitMQ client                     │
│  └── storage/         → MinIO client (with compression)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Data Layer                                                  │
│  ├── models/          → SQLAlchemy models                   │
│  ├── repository/    → Data access layer                   │
│  └── interfaces/      → Abstract interfaces                 │
└─────────────────────────────────────────────────────────────┘
```

### Analytics Pipeline (5 Modules)

```
Raw Post → [1] Preprocessor → [2] Intent → [3] Keyword → [4] Sentiment → [5] Impact → Result
                                  │
                                  └── Skip Logic (SPAM/SEEDING → bypass AI)
```

## Core Modules

### Module 1: Text Preprocessing (`services/analytics/preprocessing/`)

- **Purpose**: Merge & normalize content from multiple sources
- **Input**: Atomic JSON (content, transcription, comments)
- **Output**: `PreprocessingResult` (clean_text, stats, source_breakdown)
- **Features**:
  - Content merging: Transcription > Caption > Top Comments
  - Unicode NFKC normalization
  - Vietnamese teencode/slang normalization
  - URL, emoji, hashtag removal
  - Spam signal detection (phone numbers, spam keywords)

### Module 2: Intent Classification (`services/analytics/intent/`)

- **Purpose**: Gatekeeper to filter noise before expensive AI
- **Categories**: CRISIS, SEEDING, SPAM, COMPLAINT, LEAD, SUPPORT, DISCUSSION
- **Performance**: <0.01ms per prediction
- **Config**: `config/intent_patterns.yaml` (YAML-based patterns)
- **Skip Logic**: SPAM/SEEDING → bypass sentiment/keyword analysis

### Module 3: Hybrid Keyword Extraction (`services/analytics/keyword/`)

- **Purpose**: Extract aspect-aware keywords
- **Approach**: 3-stage hybrid
  1. Dictionary Matching (O(n) lookup, high precision)
  2. AI Discovery (SpaCy + YAKE, high recall)
  3. Aspect Mapping (fuzzy matching to business aspects)
- **Aspects**: DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL
- **Config**: `config/aspects.yaml`

### Module 4: Aspect-Based Sentiment Analysis (`services/analytics/sentiment/`)

- **Purpose**: Overall + aspect-level sentiment
- **Model**: PhoBERT ONNX (wonrax/phobert-base-vietnamese-sentiment)
- **Features**:
  - Context windowing (±30 chars around keyword)
  - Smart boundary snapping (punctuation, pivot words: "nhưng", "tuy nhiên")
  - Weighted aggregation for multiple mentions
  - 3-class output: POSITIVE, NEGATIVE, NEUTRAL
  - Score mapping: -1.0 to 1.0

### Module 5: Impact & Risk Calculator (`services/analytics/impact/`)

- **Purpose**: Compute business impact and risk level
- **Formula**:
  ```
  EngagementScore = views×0.01 + likes×1 + comments×2 + saves×3 + shares×5
  ReachScore = log10(followers + 1) × (1.2 if verified else 1.0)
  RawImpact = EngagementScore × ReachScore × PlatformMultiplier × SentimentAmplifier
  ImpactScore = normalize(RawImpact, 0-100)
  ```
- **Risk Levels**: CRITICAL, HIGH, MEDIUM, LOW
- **Flags**: is_viral (≥70), is_kol (followers ≥50k)

## Project Conventions

### Code Style

- **Python**: PEP 8, Black formatting (line-length: 100)
- **Type Hints**: Required for all function signatures
- **Imports**: Use `# type: ignore` for third-party packages without stubs
- **Naming**:
  - Classes: PascalCase
  - Functions/variables: snake_case
  - Constants: UPPER_SNAKE_CASE (in `constants.py`)

### File Organization

- **Constants**: Centralized in `core/constants.py` and `infrastructure/ai/constants.py`
- **Configuration**: `core/config.py` (Pydantic Settings)
- **Interfaces**: `interfaces/` (Abstract base classes)
- **Models**: `models/database.py` (SQLAlchemy)

### Testing Strategy

- **Unit Tests**: Mock external dependencies, test business logic
- **Integration Tests**: Test with real models (skipped if not downloaded)
- **Performance Tests**: Benchmark critical paths
- **Test Organization**: Mirror source structure in `tests/`
- **Coverage Goal**: 80%+ on core logic
- **Commands**:
  ```bash
  make test-phobert          # All PhoBERT tests
  make test-intent           # Intent classifier tests
  make test-spacyyake        # Keyword extraction tests
  ```

### Git Workflow

- **Branching**: Feature branches from `main`
- **Commits**: Conventional commits format
- **OpenSpec**: Use for major changes (proposal → implementation → archive)

## Configuration

### Environment Variables (`.env`)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/analytics

# PhoBERT
PHOBERT_MODEL_PATH=infrastructure/phobert/models
PHOBERT_MAX_LENGTH=128

# SpaCy-YAKE
SPACY_MODEL=xx_ent_wiki_sm
YAKE_LANGUAGE=vi
MAX_KEYWORDS=30

# ABSA
CONTEXT_WINDOW_SIZE=30
THRESHOLD_POSITIVE=0.25
THRESHOLD_NEGATIVE=-0.25

# Intent
INTENT_PATTERNS_PATH=config/intent_patterns.yaml

# Impact
IMPACT_VIRAL_THRESHOLD=70.0
IMPACT_KOL_FOLLOWER_THRESHOLD=50000

# MinIO
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Compression
COMPRESSION_ENABLED=true
COMPRESSION_DEFAULT_LEVEL=2
COMPRESSION_ALGORITHM=zstd
```

## Important Constraints

- **Model Size**: Keep model artifacts out of git (use `.gitignore`)
- **Memory**: Optimize for CPU inference (no GPU required)
- **Dependencies**: Use `uv` for fast, reproducible dependency management
- **Performance Targets**:
  - Sentiment inference: <100ms
  - Intent classification: <0.01ms
  - Keyword extraction: <500ms
  - Full pipeline: <1s

## External Dependencies

| Dependency | Purpose                 | Notes                   |
| ---------- | ----------------------- | ----------------------- |
| PostgreSQL | Primary database        | Alembic migrations      |
| MinIO      | Model artifact storage  | Zstd compression        |
| RabbitMQ   | Message queue           | aio-pika client         |
| PhoBERT    | Vietnamese sentiment    | ONNX quantized (~150MB) |
| SpaCy      | NLP (NER, tokenization) | xx_ent_wiki_sm model    |
| YAKE       | Statistical keywords    | Language-agnostic       |
| PyVi       | Vietnamese segmentation | Word tokenization       |

## Directory Structure

```
analytics_engine/
├── command/                  # Entry points
│   └── consumer/             # RabbitMQ consumer (Event-Driven)
├── config/                   # YAML configurations
│   ├── aspects.yaml         # Aspect dictionary
│   └── intent_patterns.yaml # Intent patterns
├── core/                     # Core functionality
│   ├── config.py            # Pydantic Settings
│   ├── constants.py         # Global constants
│   └── logger.py            # Loguru setup
├── infrastructure/           # External integrations
│   ├── ai/                  # AI models
│   │   ├── phobert_onnx.py # PhoBERT wrapper
│   │   ├── spacyyake_extractor.py
│   │   └── constants.py    # AI constants
│   ├── messaging/           # RabbitMQ
│   └── storage/             # MinIO client
├── interfaces/               # Abstract interfaces
├── internal/                 # Implementation
│   └── consumers/           # Message handlers
├── models/                   # SQLAlchemy models
├── repository/             # Data access layer
├── services/                 # Business logic
│   └── analytics/
│       ├── orchestrator.py  # Pipeline coordinator
│       ├── preprocessing/   # Module 1
│       ├── intent/          # Module 2
│       ├── keyword/         # Module 3
│       ├── sentiment/       # Module 4
│       └── impact/          # Module 5
├── tests/                    # Test suite
├── migrations/               # Alembic migrations
├── openspec/                 # Specifications
│   ├── specs/               # Current capabilities
│   └── changes/             # Change proposals
├── document/                 # Documentation
├── examples/                 # Usage examples
└── scripts/                  # Utility scripts
```

## Existing Capabilities (Specs)

| Capability                  | Description                            |
| --------------------------- | -------------------------------------- |
| `foundation`                | Core infrastructure setup              |
| `text_preprocessing`        | Module 1: Text normalization           |
| `intent_classification`     | Module 2: Intent gatekeeper            |
| `keyword_extraction`        | Module 3: Basic keyword extraction     |
| `hybrid_keyword_extraction` | Module 3: Hybrid approach with aspects |
| `aspect_based_sentiment`    | Module 4: ABSA sentiment analysis      |
| `impact_risk`               | Module 5: Impact & risk calculation    |
| `ai_integration`            | PhoBERT ONNX integration               |
| `storage`                   | MinIO with compression                 |
| `service_lifecycle`         | Service startup/shutdown               |

## Quick Commands

```bash
# Development
make dev-up                  # Start dev services
make dev-down                # Stop dev services
make run-consumer            # Start consumer service

# Database
make db-upgrade              # Run migrations
make db-downgrade            # Rollback migration

# Models
make download-phobert        # Download PhoBERT from MinIO
make download-spacy-model    # Download SpaCy model

# Testing
make test-phobert            # PhoBERT tests (35 tests)
make test-intent             # Intent tests (52 tests)
make test-spacyyake          # SpaCy-YAKE tests (78 tests)

# Code Quality
make format                  # Format with Black
make lint                    # Lint with Ruff
```
