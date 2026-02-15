# Intent Classification Domain

Domain xử lý phân loại ý định (intent classification) cho các bài đăng trên mạng xã hội.

## Cấu trúc Domain

```
intent_classification/
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   ├── intent_classification.py  # Core business logic
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

## Kiến trúc Clean Architecture

Domain này tuân theo **Clean Architecture** và **Domain-Driven Design (DDD)**:

### 1. Delivery Layer (Tầng Giao tiếp)

**Domain này KHÔNG có Delivery Layer** vì không nhận input trực tiếp từ external sources.

### 2. Use Case Layer (Tầng Nghiệp vụ)

**Vai trò:** Chứa business logic thuần túy, độc lập với delivery mechanism.

**Trách nhiệm:**

- Phân loại ý định của văn bản (CRISIS, SEEDING, SPAM, COMPLAINT, LEAD, SUPPORT, DISCUSSION)
- Sử dụng regex patterns để match với các intent categories
- Tính toán confidence score dựa trên số lượng patterns matched
- Xác định có nên skip AI processing hay không (SPAM/SEEDING)

**Đặc điểm:**

- Không biết về RabbitMQ, HTTP hay bất kỳ protocol nào
- Có thể reuse cho nhiều delivery methods (RabbitMQ, HTTP, CLI)
- Dễ test (không phụ thuộc infrastructure)

**Ví dụ:**

```python
# usecase/intent_classification.py
class IntentClassification:
    def process(self, input_data: Input) -> Output:
        # Business logic thuần túy
        text = input_data.text

        # Match patterns
        matches = self._match_patterns(text)

        # Resolve conflicts by priority
        best_intent = self._resolve_conflicts(matches)

        # Calculate confidence
        confidence = self._calculate_confidence(matches)

        return Output(
            intent=best_intent,
            confidence=confidence,
            should_skip=best_intent in (Intent.SPAM, Intent.SEEDING),
            matched_patterns=matches[best_intent]
        )
```

### 3. Repository Layer (Tầng Truy cập Dữ liệu)

**Domain này KHÔNG có Repository Layer** vì không truy cập database.

### 4. Domain Types & Interfaces

**type.py** - Domain data structures:

```python
@dataclass
class Input:
    text: str

@dataclass
class Output:
    intent: Intent
    confidence: float
    should_skip: bool
    matched_patterns: list[str]

class Intent(Enum):
    CRISIS = 10
    SEEDING = 9
    SPAM = 8
    COMPLAINT = 7
    LEAD = 5
    SUPPORT = 4
    DISCUSSION = 1
```

**interface.py** - Domain contracts:

```python
class IIntentClassification(Protocol):
    def process(self, input_data: Input) -> Output: ...
```

## Dependency Flow (Luồng phụ thuộc)

```
Delivery → Use Case → Repository → Database
   ↓          ↓           ↓
  (RabbitMQ) (Logic)   (PostgreSQL)
  (HTTP)
```

**Nguyên tắc:** Các tầng bên trong KHÔNG phụ thuộc vào tầng bên ngoài.

**Domain này:** Chỉ có Use Case layer, được sử dụng bởi các domain khác.

## Cách sử dụng

### 1. Sử dụng trực tiếp

```python
from internal.intent_classification import New, Config, Input

config = Config(
    patterns_path="config/intent_patterns.yaml",
    confidence_threshold=0.5
)
intent_classifier = New(config)

input_data = Input(text="VinFast lừa đảo khách hàng")
output = intent_classifier.process(input_data)

print(output.intent)  # Intent.CRISIS
print(output.confidence)  # 0.6
print(output.should_skip)  # False
```

### 2. Sử dụng trong Domain khác

```python
# Trong analytics domain
from internal.intent_classification import New as NewIntentClassification, Config as IntentConfig

class AnalyticsUseCase:
    def __init__(self, deps: Dependencies):
        # Initialize intent classification with logger from dependencies
        intent_config = IntentConfig(
            patterns_path=deps.config.intent_classifier.patterns_path,
            confidence_threshold=deps.config.intent_classifier.confidence_threshold
        )
        self.intent_classifier = NewIntentClassification(intent_config, deps.logger)

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Extract text
        text = self._extract_text(data)

        # Classify intent (logger được sử dụng tự động)
        intent_input = Input(text=text)
        intent_output = self.intent_classifier.process(intent_input)

        # Skip AI processing if needed
        if intent_output.should_skip:
            return AnalyticsResult(skipped=True, reason=intent_output.intent.name)

        # Continue with sentiment analysis
        sentiment = self.sentiment.predict(text)
        ...
```

### 3. Sử dụng với Logger

```python
from pkg.logger.logger import Logger, LoggerConfig
from internal.intent_classification import New, Config, Input

# Initialize logger
logger = Logger(LoggerConfig(level="INFO", service_name="analytics"))

# Create intent classifier with logger
config = Config(patterns_path="config/intent_patterns.yaml")
intent_classifier = New(config, logger)

# Process will log automatically
input_data = Input(text="Giá xe bao nhiêu?")
output = intent_classifier.process(input_data)
```

## Intent Categories

### 1. CRISIS (Priority: 10)

- **Mô tả:** Khủng hoảng (tẩy chay, lừa đảo, scam)
- **Hành động:** Alert + Process
- **Ví dụ:** "VinFast lừa đảo khách hàng", "Tẩy chay sản phẩm này"

### 2. SEEDING (Priority: 9)

- **Mô tả:** Spam marketing (phone numbers, sales)
- **Hành động:** SKIP AI processing
- **Ví dụ:** "Inbox shop 0912345678", "Liên hệ mua hàng zalo 0987654321"

### 3. SPAM (Priority: 9)

- **Mô tả:** Garbage (vay tiền, bán sim)
- **Hành động:** SKIP AI processing
- **Ví dụ:** "Vay tiền nhanh lãi suất thấp", "Bán sim số đẹp"

### 4. COMPLAINT (Priority: 7)

- **Mô tả:** Phàn nàn sản phẩm/dịch vụ
- **Hành động:** Flag + Process
- **Ví dụ:** "Chất lượng tệ quá", "Thất vọng với sản phẩm"

### 5. LEAD (Priority: 5)

- **Mô tả:** Sales opportunity (hỏi giá, mua xe)
- **Hành động:** Flag + Process
- **Ví dụ:** "Giá xe bao nhiêu?", "Mua ở đâu?"

### 6. SUPPORT (Priority: 4)

- **Mô tả:** Technical support needed
- **Hành động:** Flag + Process
- **Ví dụ:** "Cách sạc xe điện?", "Showroom ở đâu?"

### 7. DISCUSSION (Priority: 1)

- **Mô tả:** Normal discussion (default)
- **Hành động:** Process
- **Ví dụ:** "Xe này đẹp quá", "Tôi thích màu này"

## Pattern Configuration

### Default Patterns (Hardcoded)

Patterns được định nghĩa trong `constant.py`:

```python
DEFAULT_CRISIS_PATTERNS = [
    r"tẩy\s*chay",
    r"lừa\s*đảo",
    r"scam",
    ...
]
```

### External Patterns (YAML)

Có thể load patterns từ file YAML:

```yaml
# config/intent_patterns.yaml
CRISIS:
  - "tẩy\\s*chay"
  - "lừa\\s*đảo"
  - "scam"

SEEDING:
  - "\\b0\\d{9,10}\\b"
  - "inbox.*giá"

SPAM:
  - "vay\\s*tiền"
  - "bán\\s*sim"
```

**Lưu ý:** Phải escape backslash trong YAML (`\\` thay vì `\`)

## Conflict Resolution

Khi nhiều patterns match, sử dụng priority để resolve:

```
CRISIS (10) > SEEDING (9) = SPAM (9) > COMPLAINT (7) > LEAD (5) > SUPPORT (4) > DISCUSSION (1)
```

**Ví dụ:**

```python
text = "VinFast lừa đảo, inbox 0912345678"
# Matches: CRISIS (lừa đảo) + SEEDING (0912345678)
# Result: CRISIS (higher priority)
```

## Confidence Calculation

```python
confidence = min(0.5 + (num_matches * 0.1), 1.0)
```

- Base confidence: 0.5
- Increment per match: 0.1
- Max confidence: 1.0

**Ví dụ:**

- 1 match: 0.6
- 2 matches: 0.7
- 5+ matches: 1.0

## Best Practices

1. **Separation of Concerns:** Mỗi layer có trách nhiệm riêng biệt
2. **Dependency Inversion:** Tầng trong không phụ thuộc tầng ngoài
3. **Reusability:** Use Case có thể dùng cho nhiều delivery methods
4. **Testability:** Dễ test từng layer độc lập
5. **Scalability:** Dễ thêm domain mới mà không ảnh hưởng code cũ
6. **Type Safety:** Sử dụng dataclass thay vì `Dict[str, Any]`
7. **Constants Management:** Tất cả magic strings trong `constant.py`
8. **Factory Pattern:** Sử dụng `New()` để tạo instances
9. **Logger Injection:** Logger là optional, pass từ Dependencies

## Quy tắc Domain Pattern

### 1. Cấu trúc File

```
domain/
├── usecase/              # REQUIRED: Business logic
│   ├── {domain}.py
│   ├── new.py
│   └── __init__.py
├── interface.py          # REQUIRED: Contracts (Protocol)
├── type.py              # REQUIRED: Types (dataclass)
├── constant.py          # REQUIRED: Constants
└── README.md            # REQUIRED: Documentation
```

### 2. Naming Convention

- **Use Case**: `IntentClassification`
- **Factory**: `New(config: Config, logger: Optional[Logger] = None) -> IntentClassification`
- **Output**: `Output` (KHÔNG dùng `Result` hay `IntentResult`)
- **Method**: `process()` (KHÔNG dùng `predict()` hay `classify()`)
- **Config**: `Config`
- **Interface**: `IIntentClassification`

### 3. Type Safety

```python
# ❌ BAD
def predict(self, text: str) -> Dict[str, Any]:
    ...

# ✅ GOOD
def process(self, input_data: Input) -> Output:
    ...
```

### 4. Constants Management

```python
# constant.py
INTENT_CRISIS = "CRISIS"
DEFAULT_CRISIS_PATTERNS = [...]

# Import bằng *
from .constant import *
from .type import *
```

### 5. Factory Pattern

```python
# usecase/new.py
def New(config: Config, logger: Optional[Logger] = None) -> IntentClassification:
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")
    return IntentClassification(config, logger)
```

### 6. Logger Injection

- Logger là optional parameter
- Nếu có logger, use case sẽ log các events quan trọng
- Logger instance được pass từ Dependencies (consumer server)

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
