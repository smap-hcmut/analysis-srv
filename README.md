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

| Intent | Priority | Description | Action |
|--------|----------|-------------|--------|
| **CRISIS** | 10 | Brand crisis (scam, boycott) | Alert + Process |
| **SEEDING** | 9 | Spam marketing (phone numbers) | **SKIP** |
| **SPAM** | 9 | Garbage (loans, ads) | **SKIP** |
| **COMPLAINT** | 7 | Product/service complaints | Flag + Process |
| **LEAD** | 5 | Sales opportunities | Flag + Process |
| **SUPPORT** | 4 | Technical support requests | Flag + Process |
| **DISCUSSION** | 1 | Normal discussion (default) | Process |

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
  - "\\b0\\d{9,10}\\b"  # Phone numbers
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
| Property | Value |
|----------|-------|
| **Method** | SpaCy + YAKE |
| **Features** | NER, Noun Chunks, Statistical Keywords |
| **Languages** | English (extensible) |
| **Inference Time** | <500ms |
| **Memory** | ~200-400MB |

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

---

## Test API Endpoint

The Analytics Engine provides a `/test/analytics` endpoint for testing the full analytics pipeline integration.

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
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

---
