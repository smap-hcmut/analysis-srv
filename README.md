# Analytics Engine

A high-performance analytics processing service for social media content analysis, featuring **Vietnamese sentiment analysis** powered by PhoBERT ONNX.

---

## Key Features

### Core Capabilities
- **Vietnamese Sentiment Analysis** - 5-class sentiment prediction (1-5 stars) using PhoBERT
- **ONNX Optimization** - Quantized model for fast CPU inference (<100ms)
- **Clean Architecture** - Modular design with clear separation of concerns
- **Production-Ready** - Comprehensive testing, logging, and error handling
- **Database Integration** - PostgreSQL with Alembic migrations

### AI/ML Features
- **PhoBERT ONNX** - Fine-tuned Vietnamese BERT for sentiment analysis
- **Text Segmentation** - PyVi integration for Vietnamese word segmentation
- **Batch Processing** - Efficient batch prediction support
- **Probability Distribution** - Confidence scores and full probability output
- **Model Management** - Download from MinIO, cached locally

### Performance
- **Fast Inference** - <100ms per prediction
- **Memory Efficient** - Model loaded once, reused for all requests
- **Scalable** - Stateless design, easy to horizontally scale
- **Optimized** - Quantized ONNX model for CPU deployment

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
# Run all PhoBERT tests
make test-phobert

# Run unit tests only
make test-phobert-unit

# Run integration tests (requires model)
make test-phobert-integration
```

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
| Property | Value |
|----------|-------|
| **Model** | PhoBERT (vinai/phobert-base) |
| **Task** | 5-class sentiment analysis |
| **Format** | ONNX (quantized) |
| **Size** | ~150MB |
| **Inference Time** | <100ms |
| **Memory** | ~200-300MB |

### Configuration
Constants can be customized in `infrastructure/ai/constants.py`:
```python
DEFAULT_MODEL_PATH = "infrastructure/phobert/models"
DEFAULT_MAX_LENGTH = 128
SENTIMENT_MAP = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
```

---

## Project Structure

```
analytics_engine/
├── commands/                  # Entry points
│   ├── api/                  # API service
│   └── consumer/             # Consumer service
├── core/                     # Core functionality
│   ├── config.py            # Configuration
│   └── database.py          # Database setup
├── infrastructure/           # External integrations
│   ├── ai/                  # AI models
│   │   ├── phobert_onnx.py # PhoBERT wrapper
│   │   └── constants.py    # AI constants
│   └── phobert/
│       └── models/          # Model artifacts (gitignored)
├── internal/                 # Implementation
│   └── api/                 # API layer
├── services/                 # Business logic
├── tests/                    # Test suite
│   └── phobert/             # PhoBERT tests
│       ├── test_unit.py     # 21 unit tests
│       ├── test_integration.py # 9 integration tests
│       └── test_performance.py # 6 performance tests
├── documents/                # Documentation
│   └── phobert_report.md   # Model report
├── scripts/                  # Utility scripts
│   └── download_phobert_model.sh
├── migrations/               # Alembic migrations
├── docker-compose.dev.yml   # Development environment
├── Makefile                 # Common commands
└── pyproject.toml           # Project dependencies
```

---

## Development Guide

### Available Commands

```bash
# Development Environment
make dev-up                  # Start dev services (Postgres, Redis, MinIO)
make dev-down                # Stop dev services
make dev-logs                # View dev logs

# Database
make db-upgrade              # Run migrations
make db-downgrade            # Rollback migration

# PhoBERT
make download-phobert        # Download model from MinIO
make test-phobert            # Run all tests (35 tests)
make test-phobert-unit       # Run unit tests (21 tests)
make test-phobert-integration # Run integration tests (9 tests)
make test-phobert-performance # Run performance tests (6 tests)

# API
make run-api                 # Start API service

# Code Quality
make format                  # Format code with Black
make lint                    # Lint code with flake8
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
│  Entry Points (commands/)           │
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
