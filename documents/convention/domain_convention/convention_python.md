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

### Types
- `Config`, `Input`, `Output` — dataclasses trong `type.py`
- `<Action>Options` — trong `repository/option.py`

### Errors
- Prefix `Err`: `ErrFailedToCreate`, `ErrInvalidInput`, `ErrPostNotFound`
- Mỗi layer có errors riêng

### Repository Methods
| Verb | Purpose | Example |
|------|---------|---------|
| `create` | Insert single | `create(opt: CreateOptions)` |
| `upsert` | Insert or update | `upsert(opt: UpsertOptions)` |
| `detail` | Get by PK | `detail(id: str)` |
| `get_one` | Get by filters | `get_one(opt: GetOneOptions)` |
| `list` | List no pagination | `list(opt: ListOptions)` |
| `update_status` | Update specific field | `update_status(opt: UpdateStatusOptions)` |
| `delete` | Delete | `delete(opt: DeleteOptions)` |

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
