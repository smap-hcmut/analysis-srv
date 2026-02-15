# Analytics Pipeline Domain

Domain này orchestrate toàn bộ analytics pipeline cho social media posts qua 5 giai đoạn:

1. **Text Preprocessing** - Làm sạch và chuẩn hóa text
2. **Intent Classification** - Phân loại intent (gatekeeper để filter spam/seeding)
3. **Keyword Extraction** - Trích xuất keywords và aspects
4. **Sentiment Analysis** - Phân tích sentiment (overall + aspect-based)
5. **Impact Calculation** - Tính toán impact score và risk level

## Kiến trúc 3 tầng

```
internal/analytics_pipeline/
├── interface.py              # Protocol contract (IAnalyticsPipeline)
├── type.py                   # Data structures (Config, Input, Output, AnalyticsResult)
├── constant.py               # Constants
│
├── delivery/                 # Tầng nhận message từ RabbitMQ
│   ├── analytics_handler.py  # Handler xử lý incoming messages
│   └── new.py                # Factory function
│
├── usecase/                  # Tầng business logic
│   ├── analytics_pipeline.py # Core pipeline orchestration
│   └── new.py                # Factory function
│
└── repository/               # Tầng data persistence
    ├── analytics_repository.py    # Repository cho PostAnalytics
    └── new.py                # Factory function
```

## Data Flow

```
RabbitMQ Message
    ↓
AnalyticsHandler (delivery)
    ↓ parse & validate
AnalyticsPipeline (usecase)
    ↓ run 5-stage pipeline
AnalyticsRepository (repository)
    ↓ persist to DB
PostAnalytics table
```

## Usage Example

```python
from sqlalchemy.orm import Session
from pkg.logger.logger import Logger
from internal.analytics_pipeline import (
    Config,
    NewAnalyticsRepository,
    NewAnalyticsPipeline,
    NewAnalyticsHandler,
)

# 1. Create repository
repository = NewAnalyticsRepository(db_session)

# 2. Create pipeline with AI modules
pipeline = NewAnalyticsPipeline(
    config=Config(),
    repository=repository,
    logger=logger,
    preprocessor=preprocessor,
    intent_classifier=intent_classifier,
    keyword_extractor=keyword_extractor,
    sentiment_analyzer=sentiment_analyzer,
    impact_calculator=impact_calculator,
)

# 3. Create handler
handler = NewAnalyticsHandler(pipeline=pipeline, logger=logger)

# 4. Use handler in RabbitMQ consumer
await handler.handle_message(incoming_message)
```

## Contract v2.0 Fields

Pipeline hỗ trợ đầy đủ các field trong Contract v2.0:

### Batch Context
- `job_id`, `batch_index`, `task_type`, `keyword_source`
- `crawled_at`, `pipeline_version`

### Brand/Keyword
- `brand_name`, `keyword`

### Content Fields
- `content_text`, `content_transcription`
- `media_duration`, `hashtags`, `permalink`

### Author Fields
- `author_id`, `author_name`, `author_username`
- `author_avatar_url`, `author_is_verified`

## Skip Logic

Posts sẽ được skip (không chạy AI models) nếu:
- Intent = SPAM hoặc SEEDING
- Text quá ngắn (< threshold)
- Có spam keywords

Skipped posts vẫn được lưu vào DB với neutral sentiment và low impact.

## Error Handling

- **Validation errors**: Nack message, không retry
- **Infrastructure errors** (DB, MinIO): Nack message, có retry
- **AI model errors**: Graceful degradation, lưu với default values

## Testing

```bash
# Run unit tests
pytest internal/analytics_pipeline/tests/

# Run integration tests
pytest internal/analytics_pipeline/tests/integration/
```

## Dependencies

- **AI Modules**: TextPreprocessor, IntentClassifier, KeywordExtractor, SentimentAnalyzer, ImpactCalculator
- **Infrastructure**: PostgreSQL (via SQLAlchemy), RabbitMQ (via aio-pika)
- **Logging**: pkg.logger.Logger
