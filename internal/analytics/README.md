# Analytics Domain

Domain xử lý phân tích dữ liệu (sentiment analysis, keyword extraction) từ các events thu thập được.

## Cấu trúc Domain

```
analytics/
├── delivery/              # Tầng giao tiếp (Delivery Layer)
│   ├── rabbitmq/         # RabbitMQ consumer handlers
│   │   └── handler.py    # Handler nhận và parse messages
│   └── http/             # HTTP handlers (future)
│       └── handler.py    # REST API endpoints
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   └── analytics.py      # Core business logic
├── repository/           # Tầng truy cập dữ liệu (Data Access Layer)
│   └── postgre.py        # PostgreSQL operations
├── interface.py          # Domain interfaces (contracts)
└── type.py              # Domain types (data structures)
```

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
class AnalyticsHandler:
    async def handle(self, message: IncomingMessage):
        # 1. Parse RabbitMQ message
        data = json.loads(message.body)

        # 2. Delegate to use case
        await self.usecase.process_analytics(data)

        # 3. Handle ack/nack (protocol-specific)
```

**Mở rộng với HTTP:**

```python
# delivery/http/handler.py
class AnalyticsHTTPHandler:
    async def analyze_text(self, request: Request):
        # 1. Parse HTTP request
        data = await request.json()

        # 2. Delegate to use case
        result = await self.usecase.process_analytics(data)

        # 3. Return HTTP response
        return JSONResponse(result)
```

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
# usecase/analytics.py
class AnalyticsUseCase:
    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Business logic thuần túy
        text = self._extract_text(data)
        sentiment = self.sentiment.predict(text)
        keywords = self.keyword_extractor.extract(text)

        # Store results
        await self.repository.save_result(...)

        return AnalyticsResult(...)
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
class AnalyticsRepository:
    async def save_result(self, result: AnalyticsResult):
        # Database-specific logic
        query = "INSERT INTO analytics_results ..."
        await self.db.execute(query, ...)

    async def get_by_id(self, message_id: str) -> AnalyticsResult:
        # Query and map to domain object
        ...
```

### 4. Domain Types & Interfaces

**Vai trò:** Define contracts và data structures cho domain.

**type.py** - Domain data structures:

```python
@dataclass
class AnalyticsResult:
    message_id: str
    sentiment: str
    keywords: list[str]
```

**interface.py** - Domain contracts:

```python
class IAnalyticsUseCase(Protocol):
    async def process_analytics(self, data: dict) -> AnalyticsResult: ...
```

## Dependency Flow (Luồng phụ thuộc)

```
Delivery → Use Case → Repository → Database
   ↓          ↓           ↓
  (RabbitMQ) (Logic)   (PostgreSQL)
  (HTTP)
```

**Nguyên tắc:** Các tầng bên trong KHÔNG phụ thuộc vào tầng bên ngoài.

- Use Case không biết về Delivery (RabbitMQ hay HTTP)
- Repository không biết về Use Case
- Domain types không phụ thuộc vào bất kỳ tầng nào

## Cách sử dụng

### 1. RabbitMQ Consumer (hiện tại)

Handler được load tự động bởi `MultiQueueConsumerServer`:

```yaml
# config/config.yaml
rabbitmq:
  queues:
    - name: "analytics.data.collected"
      exchange: "smap.events"
      routing_key: "data.collected"
      handler_module: "internal.analytics.delivery.rabbitmq.handler"
      handler_class: "AnalyticsHandler"
      prefetch_count: 10
      enabled: true
```

### 2. HTTP Server (future)

Có thể thêm HTTP endpoints sử dụng cùng Use Case:

```python
# delivery/http/handler.py
from internal.analytics.usecase import AnalyticsUseCase

class AnalyticsHTTPHandler:
    def __init__(self, deps: Dependencies):
        self.usecase = AnalyticsUseCase(deps)  # Reuse use case

    async def analyze_text(self, request: Request):
        data = await request.json()
        result = await self.usecase.process_analytics(data)
        return JSONResponse(result.dict())
```

```python
# apps/api/main.py (HTTP server)
from fastapi import FastAPI
from internal.analytics.delivery.http import AnalyticsHTTPHandler

app = FastAPI()
handler = AnalyticsHTTPHandler(deps)

@app.post("/analytics/analyze")
async def analyze(request: Request):
    return await handler.analyze_text(request)
```

## Thêm Domain mới

Để thêm domain mới (ví dụ: `notification`):

```
internal/
├── analytics/          # Domain hiện tại
└── notification/       # Domain mới
    ├── delivery/
    │   ├── rabbitmq/
    │   │   └── handler.py
    │   └── http/
    │       └── handler.py
    ├── usecase/
    │   └── notification.py
    ├── repository/
    │   └── postgre.py
    ├── interface.py
    └── type.py
```

**Config:**

```yaml
rabbitmq:
  queues:
    - name: "notification.events"
      handler_module: "internal.notification.delivery.rabbitmq.handler"
      handler_class: "NotificationHandler"
```

Server tự động load và start consuming!

## Best Practices

1. **Separation of Concerns:** Mỗi layer có trách nhiệm riêng biệt
2. **Dependency Inversion:** Tầng trong không phụ thuộc tầng ngoài
3. **Reusability:** Use Case có thể dùng cho nhiều delivery methods
4. **Testability:** Dễ test từng layer độc lập
5. **Scalability:** Dễ thêm domain mới mà không ảnh hưởng code cũ

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
