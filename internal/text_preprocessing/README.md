# Text Preprocessing Domain

Domain xử lý tiền xử lý văn bản (text preprocessing) cho analytics pipeline.

## Cấu trúc Domain

```
text_preprocessing/
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   ├── text_processing.py  # Core business logic
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

**Vai trò:** Nhận input từ bên ngoài (RabbitMQ, HTTP, gRPC) và chuyển đổi thành domain objects.

**Trách nhiệm:**

- Parse và validate message format
- Handle protocol-specific logic (RabbitMQ ack/nack, HTTP status codes)
- Convert external data → domain types
- Delegate processing to Use Case layer

**Ví dụ:**

```python
# delivery/rabbitmq/handler.py
class TextProcessingHandler:
    async def handle(self, message: IncomingMessage):
        # 1. Parse RabbitMQ message
        data = json.loads(message.body)

        # 2. Convert to domain Input
        input_data = Input(...)

        # 3. Delegate to use case
        output = self.usecase.process(input_data)

        # 4. Handle ack/nack (protocol-specific)
```

**Domain này KHÔNG có Delivery Layer** vì không nhận input trực tiếp từ external sources.

### 2. Use Case Layer (Tầng Nghiệp vụ)

**Vai trò:** Chứa business logic thuần túy, độc lập với delivery mechanism.

**Trách nhiệm:**

- Orchestrate business workflows
- Validate business rules
- Coordinate between repositories và external services
- Return domain results

**Đặc điểm:**

- Không biết về RabbitMQ, HTTP hay bất kỳ protocol nào
- Có thể reuse cho nhiều delivery methods (RabbitMQ, HTTP, CLI)
- Dễ test (không phụ thuộc infrastructure)

**Ví dụ:**

```python
# usecase/text_processing.py
class TextProcessing:
    def process(self, input_data: Input) -> Output:
        # Business logic thuần túy
        merged_text = self.merge_content(...)
        clean_text = self.normalize(merged_text)
        stats = self.calculate_stats(...)

        return Output(...)
```

### 3. Repository Layer (Tầng Truy cập Dữ liệu)

**Vai trò:** Abstract data access, che giấu chi tiết database implementation.

**Trách nhiệm:**

- CRUD operations
- Query building
- Transaction management
- Convert database records ↔ domain objects

**Ví dụ:**

```python
# repository/postgre.py
class TextProcessingRepository:
    async def save_result(self, output: Output):
        query = "INSERT INTO text_processing_results ..."
        await self.db.execute(query, ...)
```

**Domain này KHÔNG có Repository Layer** vì không truy cập database.

### 4. Domain Types & Interfaces

**type.py** - Domain data structures:

```python
@dataclass
class Input:
    content: ContentInput
    comments: list[CommentInput]

@dataclass
class Output:
    clean_text: str
    stats: Stats
    source_breakdown: SourceBreakdown
```

**interface.py** - Domain contracts:

```python
class ITextProcessing(Protocol):
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
from internal.text_preprocessing import New, Config, Input, ContentInput, CommentInput

config = Config(min_text_length=10, max_comments=5)
text_processing = New(config)

input_data = Input(
    content=ContentInput(text="Amazing product! #musthave"),
    comments=[CommentInput(text="Great!", likes=15)]
)

output = text_processing.process(input_data)
print(output.clean_text)
```

### 2. Sử dụng trong Domain khác

```python
# Trong analytics domain
from internal.text_preprocessing import New as NewTextProcessing, Config as TextProcessingConfig

class AnalyticsUseCase:
    def __init__(self, deps: Dependencies):
        # Initialize text processing with logger from dependencies
        text_config = TextProcessingConfig(
            min_text_length=deps.config.preprocessor.min_text_length,
            max_comments=deps.config.preprocessor.max_comments
        )
        self.text_processing = NewTextProcessing(text_config, deps.logger)

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Convert dict to Input struct
        input_data = Input(...)

        # Preprocess text (logger được sử dụng tự động)
        output = self.text_processing.process(input_data)

        # Use clean text for sentiment analysis
        sentiment = self.sentiment.predict(output.clean_text)
        ...
```

## Thêm Domain mới

```
internal/
├── text_preprocessing/  # Utility domain
├── analytics/          # Domain với đầy đủ 3 tầng
└── notification/       # Domain mới
    ├── delivery/       # Tầng giao tiếp
    │   └── rabbitmq/
    │       └── handler.py
    ├── usecase/        # Tầng nghiệp vụ
    │   ├── notification.py
    │   ├── new.py
    │   └── __init__.py
    ├── repository/     # Tầng truy cập dữ liệu
    │   └── postgre.py
    ├── interface.py
    ├── type.py
    ├── constant.py
    └── README.md
```

## Best Practices

1. **Separation of Concerns:** Mỗi layer có trách nhiệm riêng biệt
2. **Dependency Inversion:** Tầng trong không phụ thuộc tầng ngoài
3. **Reusability:** Use Case có thể dùng cho nhiều delivery methods
4. **Testability:** Dễ test từng layer độc lập
5. **Scalability:** Dễ thêm domain mới mà không ảnh hưởng code cũ
6. **Type Safety:** Sử dụng dataclass thay vì `Dict[str, Any]`
7. **Constants Management:** Tất cả magic strings trong `constant.py`
8. **Factory Pattern:** Sử dụng `New()` để tạo instances

## Quy tắc Domain Pattern

### 1. Cấu trúc File (Đầy đủ 3 tầng)

```
domain/
├── delivery/             # OPTIONAL: RabbitMQ/HTTP handlers
│   ├── rabbitmq/
│   │   └── handler.py
│   └── http/
│       └── handler.py
├── usecase/              # REQUIRED: Business logic
│   ├── {domain}.py
│   ├── new.py
│   └── __init__.py
├── repository/           # OPTIONAL: Database operations
│   └── postgre.py
├── interface.py          # REQUIRED: Contracts (Protocol)
├── type.py              # REQUIRED: Types (dataclass)
├── constant.py          # REQUIRED: Constants
└── README.md            # REQUIRED: Documentation
```

### 2. Naming Convention

- **Use Case**: `{Domain}` (e.g., `TextProcessing`)
- **Factory**: `New(config: Config) -> {Domain}`
- **Output**: `Output` (KHÔNG dùng `Result`)
- **Method**: `process()` (KHÔNG dùng `preprocess()`)
- **Config**: `Config`
- **Interface**: `I{Domain}`

### 3. Type Safety

```python
# ❌ BAD
def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
    ...

# ✅ GOOD
def process(self, data: Input) -> Output:
    ...
```

### 4. Constants Management

```python
# constant.py
FIELD_CONTENT = "content"
PATTERN_URL = r"http[s]?://..."

# Import bằng *
from .constant import *
from .type import *
```

**Quy tắc import:**
- Constants: `from .constant import *`
- Types: `from .type import *`
- Giảm boilerplate code
- Dễ maintain khi thêm constants/types mới

### 5. Factory Pattern

```python
# usecase/new.py
def New(config: Config, logger: Optional[Logger] = None) -> TextProcessing:
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")
    return TextProcessing(config, logger)
```

**Logger injection:**

- Logger là optional parameter
- Nếu có logger, use case sẽ log các events quan trọng
- Logger instance được pass từ Dependencies (consumer server)

### 6. Layer Responsibilities

**Delivery:** Parse, convert, delegate (KHÔNG có business logic)
**Use Case:** Business logic thuần túy (KHÔNG biết về protocols)
**Repository:** Database operations (KHÔNG có business logic)

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
