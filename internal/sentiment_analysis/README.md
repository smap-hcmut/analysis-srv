# Sentiment Analysis Domain

Domain xử lý phân tích cảm xúc (sentiment analysis) với aspect-based sentiment analysis (ABSA) cho analytics pipeline.

## Cấu trúc Domain

```
sentiment_analysis/
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   ├── sentiment_analysis.py  # Core business logic
│   ├── new.py            # Factory function
│   └── __init__.py
├── interface.py          # Domain interfaces (contracts)
├── type.py              # Domain types (data structures)
├── constant.py          # Domain constants
└── README.md            # Documentation
```

**Lưu ý:** Domain này KHÔNG có Delivery Layer và Repository Layer vì:

- Không nhận input trực tiếp từ RabbitMQ/HTTP (không có delivery)
- Không truy cập database (không có repository)
- Chỉ là utility domain được sử dụng bởi các domain khác

## Approach: Aspect-Based Sentiment Analysis (ABSA)

### 1. Overall Sentiment
Phân tích cảm xúc tổng thể cho toàn bộ văn bản.

### 2. Aspect-Based Sentiment
Phân tích cảm xúc cho từng aspect sử dụng context windowing:
- Extract context window xung quanh keyword
- Predict sentiment cho context
- Aggregate results cho multiple mentions

### 3. Context Windowing
Smart boundary snapping:
- Configurable radius xung quanh keyword
- Trim tới delimiters gần nhất (punctuation, pivot words)
- Snap tới word boundaries

## Cách sử dụng

### 1. Sử dụng trực tiếp

```python
from internal.sentiment_analysis import New, Config, Input, KeywordInput
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.phobert_onnx.type import PhoBERTConfig

# Initialize PhoBERT
phobert_config = PhoBERTConfig(model_path="internal/model/phobert")
phobert_model = PhoBERTONNX(phobert_config)

# Initialize sentiment analysis
config = Config(
    context_window_size=100,
    threshold_positive=0.25,
    threshold_negative=-0.25
)
sentiment_analysis = New(config, phobert_model)

# Analyze overall sentiment
input_data = Input(text="Xe đẹp nhưng pin yếu quá")
output = sentiment_analysis.process(input_data)
print(output.overall.label)  # NEUTRAL

# Analyze aspect-based sentiment
keywords = [
    KeywordInput(keyword="xe", aspect="DESIGN"),
    KeywordInput(keyword="pin", aspect="PERFORMANCE"),
]
input_data = Input(text="Xe đẹp nhưng pin yếu quá", keywords=keywords)
output = sentiment_analysis.process(input_data)

for aspect, sentiment in output.aspects.items():
    print(f"{aspect}: {sentiment.label}")
```

### 2. Sử dụng trong Domain khác

```python
# Trong analytics domain
from internal.sentiment_analysis import New as NewSentimentAnalysis, Config as SentimentConfig

class AnalyticsUseCase:
    def __init__(self, deps: Dependencies):
        # Initialize sentiment analysis with PhoBERT from dependencies
        sentiment_config = SentimentConfig(
            context_window_size=100,
            threshold_positive=0.25,
            threshold_negative=-0.25
        )
        self.sentiment_analysis = NewSentimentAnalysis(
            sentiment_config,
            deps.sentiment,  # PhoBERTONNX from Dependencies
            deps.logger
        )

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Extract text and keywords
        text = self._extract_text(data)
        keywords = self._extract_keywords(text)
        
        # Analyze sentiment
        sentiment_input = Input(text=text, keywords=keywords)
        sentiment_output = self.sentiment_analysis.process(sentiment_input)
        
        # Use results
        print(f"Overall: {sentiment_output.overall.label}")
        for aspect, sentiment in sentiment_output.aspects.items():
            print(f"{aspect}: {sentiment.label}")
```

## Sentiment Labels

### 3-Class ABSA Format
- **POSITIVE**: score > 0.25
- **NEGATIVE**: score < -0.25
- **NEUTRAL**: -0.25 ≤ score ≤ 0.25

### Score Mapping (5-star → sentiment score)
- Rating 1: -1.0 (Very negative)
- Rating 2: -0.5 (Negative)
- Rating 3: 0.0 (Neutral)
- Rating 4: 0.5 (Positive)
- Rating 5: 1.0 (Very positive)

## Dependency Injection

Domain này cần **PhoBERTONNX instance** được inject vào constructor (giống keyword_extraction).

**Signature:**
```python
def New(
    config: Config,
    phobert_model: PhoBERTONNX,  # ← CẦN INJECT
    logger: Optional[Logger] = None
) -> SentimentAnalysis
```

**Lý do:**
1. PhoBERTONNX đã được khởi tạo trong `Dependencies`
2. PhoBERT nặng (~100MB models), không nên tạo nhiều instances
3. Reuse instance từ Dependencies

## Best Practices

1. **Separation of Concerns:** Mỗi layer có trách nhiệm riêng biệt
2. **Dependency Inversion:** Tầng trong không phụ thuộc tầng ngoài
3. **Reusability:** Use Case có thể dùng cho nhiều delivery methods
4. **Testability:** Dễ test từng layer độc lập
5. **Type Safety:** Sử dụng dataclass thay vì `Dict[str, Any]`
6. **Constants Management:** Tất cả magic strings trong `constant.py`
7. **Factory Pattern:** Sử dụng `New()` để tạo instances
8. **Logger Injection:** Logger là optional, pass từ Dependencies
9. **Dependency Injection:** PhoBERT được inject, không tạo trong usecase

## Naming Convention

- **Use Case**: `SentimentAnalysis`
- **Factory**: `New(config: Config, phobert_model: PhoBERTONNX, logger: Optional[Logger] = None) -> SentimentAnalysis`
- **Output**: `Output` (KHÔNG dùng `Result`)
- **Method**: `process()` (KHÔNG dùng `analyze()`)
- **Config**: `Config`
- **Interface**: `ISentimentAnalysis`

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
