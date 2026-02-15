# Keyword Extraction Domain

Domain xử lý trích xuất từ khóa (keyword extraction) với aspect mapping cho analytics pipeline.

## Cấu trúc Domain

```
keyword_extraction/
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   ├── keyword_extraction.py  # Core business logic
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

- Trích xuất từ khóa từ văn bản sử dụng hybrid approach (Dictionary + AI)
- Map từ khóa vào business aspects (DESIGN, PERFORMANCE, PRICE, SERVICE)
- Kết hợp dictionary matching (precision) với AI discovery (recall)
- Tính toán scores và metadata

**Đặc điểm:**

- Không biết về RabbitMQ, HTTP hay bất kỳ protocol nào
- Có thể reuse cho nhiều delivery methods (RabbitMQ, HTTP, CLI)
- Dễ test (không phụ thuộc infrastructure)
- Dependency injection cho AI extractor (SpacyYake)

**Ví dụ:**

```python
# usecase/keyword_extraction.py
class KeywordExtraction:
    def process(self, input_data: Input) -> Output:
        # Stage 1: Dictionary Matching
        dict_keywords = self._match_dictionary(text)

        # Stage 2: AI Discovery (if needed)
        if len(dict_keywords) < threshold:
            ai_keywords = self._extract_ai(text)

        # Stage 3: Aspect Mapping
        for kw in ai_keywords:
            kw.aspect = self._fuzzy_map_aspect(kw.keyword)

        return Output(keywords=all_keywords, metadata=metadata)
```

### 3. Repository Layer (Tầng Truy cập Dữ liệu)

**Domain này KHÔNG có Repository Layer** vì không truy cập database.

**Lưu ý:** Nếu cần cache hoặc dynamic aspect mapping từ database, có thể thêm repository layer sau.

### 4. Domain Types & Interfaces

**type.py** - Domain data structures:

```python
@dataclass
class Input:
    text: str

@dataclass
class KeywordItem:
    keyword: str
    aspect: str
    score: float
    source: str  # "DICT" or "AI"

@dataclass
class Output:
    keywords: list[KeywordItem]
    metadata: Metadata

class Aspect(Enum):
    DESIGN = "DESIGN"
    PERFORMANCE = "PERFORMANCE"
    PRICE = "PRICE"
    SERVICE = "SERVICE"
    GENERAL = "GENERAL"
```

**interface.py** - Domain contracts:

```python
class IKeywordExtraction(Protocol):
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
from internal.keyword_extraction import New, Config, Input
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig

# Initialize AI extractor
ai_config = SpacyYakeConfig(
    spacy_model="xx_ent_wiki_sm",
    yake_language="vi",
    max_keywords=30
)
ai_extractor = SpacyYake(ai_config)

# Initialize keyword extraction
config = Config(
    aspect_dictionary_path="config/aspects_patterns.yaml",
    enable_ai=True,
    ai_threshold=5,
    max_keywords=30
)
keyword_extraction = New(config, ai_extractor)

# Extract keywords
input_data = Input(text="Xe đẹp nhưng pin yếu quá")
output = keyword_extraction.process(input_data)

for kw in output.keywords:
    print(f"{kw.keyword} → {kw.aspect} ({kw.source})")
```

### 2. Sử dụng trong Domain khác

```python
# Trong analytics domain
from internal.keyword_extraction import New as NewKeywordExtraction, Config as KeywordConfig

class AnalyticsUseCase:
    def __init__(self, deps: Dependencies):
        # Initialize keyword extraction with logger and AI extractor from dependencies
        keyword_config = KeywordConfig(
            aspect_dictionary_path=deps.config.keyword_extraction.aspect_dictionary_path,
            enable_ai=True,
            ai_threshold=5,
            max_keywords=deps.config.keyword_extraction.max_keywords
        )
        self.keyword_extraction = NewKeywordExtraction(
            keyword_config,
            deps.keyword_extractor,  # SpacyYake from Dependencies
            deps.logger
        )

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Extract text
        text = self._extract_text(data)

        # Extract keywords (logger được sử dụng tự động)
        keyword_input = Input(text=text)
        keyword_output = self.keyword_extraction.process(keyword_input)

        # Use keywords for analytics
        for kw in keyword_output.keywords:
            print(f"{kw.keyword} → {kw.aspect}")
        ...
```

### 3. Sử dụng với Logger

```python
from pkg.logger.logger import Logger, LoggerConfig
from internal.keyword_extraction import New, Config, Input

# Initialize logger
logger = Logger(LoggerConfig(level="INFO", service_name="analytics"))

# Create keyword extraction with logger
config = Config(aspect_dictionary_path="config/aspects_patterns.yaml")
keyword_extraction = New(config, ai_extractor, logger)

# Process will log automatically
input_data = Input(text="Xe đẹp nhưng pin yếu")
output = keyword_extraction.process(input_data)
```

## Hybrid Approach

### Stage 1: Dictionary Matching (High Precision)

Fast O(n) lookup trong aspect dictionary:

```python
# config/aspects_patterns.yaml
PERFORMANCE:
  primary:
    - "pin"
    - "sạc"
    - "động cơ"
  secondary:
    - "pin yếu"
    - "sạc nhanh"
```

**Ưu điểm:**

- Nhanh (~1-2ms)
- Chính xác 100% cho known terms
- Aspect mapping sẵn

### Stage 2: AI Discovery (High Recall)

Sử dụng SpaCy + YAKE để discover new keywords:

```python
# Chỉ chạy AI nếu dictionary matches < threshold
if len(dict_keywords) < ai_threshold:
    ai_keywords = self._extract_ai(text)
```

**Ưu điểm:**

- Discover new/emerging keywords
- Không bị giới hạn bởi dictionary
- Capture entities và noun chunks

**Nhược điểm:**

- Chậm hơn (~50-100ms)
- Cần aspect mapping thêm

### Stage 3: Aspect Mapping

Map AI-discovered keywords vào aspects:

```python
def _fuzzy_map_aspect(self, keyword: str) -> Aspect:
    # Exact match
    if keyword in self.keyword_map:
        return self.keyword_map[keyword]

    # Substring match
    for term, aspect in self.keyword_map.items():
        if term in keyword or keyword in term:
            return aspect

    # Fallback
    return Aspect.GENERAL
```

## Aspect Categories

### 1. DESIGN

- **Mô tả:** Exterior/interior appearance, aesthetics
- **Keywords:** thiết kế, ngoại thất, nội thất, màu xe, đèn, ghế ngồi
- **Ví dụ:** "Xe đẹp", "Nội thất sang trọng"

### 2. PERFORMANCE

- **Mô tả:** Battery, charging, speed, technical issues
- **Keywords:** pin, sạc, động cơ, tốc độ, phanh, giảm xóc
- **Ví dụ:** "Pin yếu", "Sạc nhanh", "Động cơ khỏe"

### 3. PRICE

- **Mô tả:** Cost, value, affordability
- **Keywords:** giá, tiền, chi phí, lăn bánh, trả góp
- **Ví dụ:** "Giá đắt", "Chi phí cao", "Trả góp"

### 4. SERVICE

- **Mô tả:** Customer service, warranty, support
- **Keywords:** bảo hành, nhân viên, showroom, hỗ trợ
- **Ví dụ:** "Bảo hành tốt", "Nhân viên nhiệt tình"

### 5. GENERAL

- **Mô tả:** Default for unclassified keywords
- **Ví dụ:** "xe", "mua", "dùng"

## Performance

### Dictionary Matching

- **Time:** ~1-2ms
- **Complexity:** O(n) where n = number of words in text
- **Accuracy:** 100% for known terms

### AI Discovery (SpaCy + YAKE)

- **Time:** ~50-100ms
- **Complexity:** O(n²) for YAKE algorithm
- **Accuracy:** ~70-80% (depends on text quality)

### Hybrid Approach

- **Time:** 1-2ms (dict only) or 50-100ms (dict + AI)
- **Precision:** High (dictionary)
- **Recall:** High (AI discovery)

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
10. **Dependency Injection:** AI extractor được inject, không tạo trong usecase

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

- **Use Case**: `KeywordExtraction`
- **Factory**: `New(config: Config, ai_extractor: SpacyYake, logger: Optional[Logger] = None) -> KeywordExtraction`
- **Output**: `Output` (KHÔNG dùng `Result` hay `KeywordResult`)
- **Method**: `process()` (KHÔNG dùng `extract()`)
- **Config**: `Config`
- **Interface**: `IKeywordExtraction`

### 3. Type Safety

```python
# ❌ BAD
def extract(self, text: str) -> Dict[str, Any]:
    ...

# ✅ GOOD
def process(self, input_data: Input) -> Output:
    ...
```

### 4. Constants Management

```python
# constant.py
ASPECT_DESIGN = "DESIGN"
SOURCE_DICT = "DICT"

# Import bằng *
from .constant import *
from .type import *
```

### 5. Factory Pattern

```python
# usecase/new.py
def New(
    config: Config,
    ai_extractor: SpacyYake,
    logger: Optional[Logger] = None
) -> KeywordExtraction:
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")
    if not isinstance(ai_extractor, SpacyYake):
        raise ValueError("ai_extractor must be an instance of SpacyYake")
    return KeywordExtraction(config, ai_extractor, logger)
```

### 6. Dependency Injection

- AI extractor (SpacyYake) được inject từ Dependencies
- Logger là optional parameter
- Config được extract từ Dependencies

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
