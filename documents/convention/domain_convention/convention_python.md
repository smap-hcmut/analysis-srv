# Python Convention — Adapted from Go Architecture

Tài liệu này mô tả convention đã được adapt từ Go sang Python cho repo `analysis-srv`.

---

## 1. Module Structure (internal/)

Mỗi domain module tuân theo cấu trúc:

```
internal/<module>/
├── __init__.py          # Exports: Interface, Types, Errors, New factory
├── interface.py         # Protocol definition (@runtime_checkable)
├── type.py              # ALL Input/Output/Config dataclasses
├── constant.py          # Constants, defaults, magic strings
├── errors.py            # Module-specific sentinel errors
├── usecase/
│   ├── __init__.py      # Re-exports
│   ├── new.py           # Factory ONLY: New() function
│   ├── <method>.py      # Each public method in its own file
│   └── helpers.py       # ALL private helper functions
├── delivery/            # Delivery layer (RabbitMQ, HTTP, Kafka)
│   ├── type.py          # Delivery DTOs (decoupled from domain types)
│   ├── constant.py      # Delivery-specific constants
│   └── rabbitmq/consumer/
│       ├── new.py       # Handler factory
│       └── handler.py   # Message handler (thin layer)
└── repository/          # Data access layer
    ├── __init__.py      # Re-exports
    ├── interface.py     # Repository Protocol
    ├── option.py        # ALL Options dataclasses
    ├── errors.py        # Repository-specific errors
    ├── new.py           # Factory function
    └── postgre/
        ├── new.py                    # Factory
        ├── <entity>.py               # Coordinator (execute + map)
        ├── <entity>_query.py         # Query builder (pure logic)
        └── helpers.py                # Data sanitization, UUID validation
```

## 2. Naming Conventions

### Interface

- Prefix `I`: `IAnalyticsPipeline`, `IAnalyzedPostRepository`
- Dùng `Protocol` với `@runtime_checkable`

### Factory

- Function `New()` trong `new.py`
- Trả về instance, inject dependencies

#### 2.1.1 Domain UseCase Pattern (Generic for all `internal/<domain>` modules)

- `interface.py`:
  - Định nghĩa interface `I<Domain>UseCase(Protocol)` với các method public (`create(...)`, `update(...)`, v.v.).
- `type.py`:
  - Định nghĩa mọi `Create<Domain>Input`, `Update<Domain>Input`, `Config`, `Output` dataclasses, có `to_dict()` hoặc helper tương ứng để chuẩn hoá dữ liệu cho repository / delivery.
- `usecase/usecase.py`:
  - Implement class `<Domain>UseCase(I<Domain>UseCase)`:
    - Giữ tất cả dependencies đã được inject (repository, logger, các usecase khác, v.v.).
    - Mỗi public method (`create`, `update`, ...) là thin wrapper, delegating sang hàm cùng tên trong file riêng (e.g. `create.py`, `update.py`) với chữ ký chuẩn, ví dụ:
      - `async def create(self, input_data: Create<Domain>Input) -> <Domain>Model: ...`
- `usecase/<method>.py`:
  - Chứa logic chi tiết cho từng method, luôn nhận `self` là implementation + input DTO.
  - Gọi repository qua interface (`I<Domain>Repository`) và log bằng `logger` nếu có.
- `usecase/new.py`:
  - Factory duy nhất cho toàn domain:
    - `def New(repository: I<Domain>Repository, logger: Optional[Logger] = None, ...) -> I<Domain>UseCase: ...`
  - Trả về instance `<Domain>UseCase`, nhưng type hint luôn là interface (`I<Domain>UseCase`), mirror với pattern `New(...) UseCase` trong Go (`term/internal/indexing`).
- `__init__.py` (module root):
  - Re-export interface, types, errors, và alias factory:
    - `from .usecase.new import New as New<Domain>UseCase`
  - `__all__` bao gồm `I<Domain>UseCase`, các Input/Output types, error types, và `New<Domain>UseCase`.

Pattern này áp dụng cho **mọi domain** trong `internal/` (ví dụ: `post_insight`, `analyzed_post`, `analytics`, v.v.), không gắn với 1 domain cụ thể.

### Types

- `Config`, `Input`, `Output` — dataclasses trong `type.py`
- `<Action>Options` — trong `repository/option.py`

### Errors

- Prefix `Err`: `ErrFailedToCreate`, `ErrInvalidInput`, `ErrPostNotFound`
- Mỗi layer có errors riêng

### Repository Methods

| Verb            | Purpose               | Example                                   |
| --------------- | --------------------- | ----------------------------------------- |
| `create`        | Insert single         | `create(opt: CreateOptions)`              |
| `upsert`        | Insert or update      | `upsert(opt: UpsertOptions)`              |
| `detail`        | Get by PK             | `detail(id: str)`                         |
| `get_one`       | Get by filters        | `get_one(opt: GetOneOptions)`             |
| `list`          | List no pagination    | `list(opt: ListOptions)`                  |
| `update_status` | Update specific field | `update_status(opt: UpdateStatusOptions)` |
| `delete`        | Delete                | `delete(opt: DeleteOptions)`              |

## 3. pkg/ Convention (4 file bắt buộc)

```
pkg/<name>/
├── interface.py     # Protocol definition
├── type.py          # Config, impl types
├── constant.py      # Constants
└── <name>.py        # Implementation
```

- Interface trong `interface.py`, KHÔNG inline trong implementation file
- Constructor trả về instance, inject config
- Client/dependency dùng pointer (reference)

## 4. Key Rules

1. **Delivery layer KHÔNG chứa business logic** — chỉ parse, validate, gọi usecase
2. **UseCase KHÔNG import framework** — không import aio_pika, sqlalchemy trực tiếp
3. **Repository dùng Options pattern** — không pass individual fields
4. **Repository trả về domain model** — không trả raw DB types
5. **Not found → return None** — không raise error
6. **Mỗi file một job** — types trong type.py, logic trong method files
7. **new.py chỉ là factory** — không chứa interfaces, constants, helpers

### 4.1 Logging Convention (Domain / UseCase)

- **Mục tiêu**:
  - Log đủ context để debug, không spam.
  - Thống nhất format để dễ grep / search.

- **Định dạng message**:
  - **Prefix**: `"[<Domain>UseCase] <Action> ..."` hoặc `"[<Domain>] <Action> ..."` cho các hàm thuần.
  - Ví dụ:
    - `"[PostInsightUseCase] Creating post_insight record"`
    - `"[TextPreprocessing] Processing started"`
    - `"[TextPreprocessing] Processing completed"`

- **Log info**:
  - Chỉ log **các sự kiện chính**:
    - Bắt đầu xử lý: input size, id, source_id, platform, v.v.
    - Kết thúc: id tạo ra, cờ `is_too_short`, `has_spam`, ratios, v.v.
  - Sử dụng `extra={...}` để ghi thêm structured fields:
    - Ví dụ `extra={"project_id": input.project_id, "source_id": input.source_id}`.

- **Log error (bắt buộc)**:
  - Không dùng f-string trong message, luôn dùng **format string + args** hoặc structured logging:
    - Format string + args (domain/usecase + location):
      - `self.logger.error("internal.post_insight.usecase.create: %s", e)`
    - Structured (message cố định + `extra`):
      - `logger.error("[TextPreprocessing] Processing failed", extra={"error": str(e), "error_type": type(e).__name__})`
  - Sau khi log, **luôn**:
    - Raise lại error domain (`ErrFailedToCreate`, `ErrFailedToUpdate`, ...) hoặc re-raise exception gốc nếu muốn bubble lên.

- **Không làm**:
  - Không log raw payload quá lớn.
  - Không log password/token/secrets.
  - Không sử dụng format không thống nhất (ví dụ lúc thì `"TextPreprocessing - start"`, lúc thì `"[TextPreprocessing] start"`).
