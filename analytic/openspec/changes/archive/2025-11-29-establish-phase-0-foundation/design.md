# Design: Phase 0 Foundation

## Architectural Pattern

We follow a **Layered Architecture** with clear separation between entry points, implementation, and shared functionality.

### Layers

1.  **Command Layer (`cmd/`)**: Entry points that load config, initialize instances, and start services.
2.  **Internal Layer (`internal/`)**: Service implementation - registers routes (API) and consumers (message queue).
3.  **Core Layer (`core/`)**: Shared functionality - config, models, logger, dependencies.
4.  **Services Layer (`services/`)**: Business logic (future implementation).

### Dependency Flow

```
cmd/analytics_api/main.py (entry point)
    ↓ loads
core/config.py, core/logger.py
    ↓ imports
internal/api/main.py (route registration)
    ↓ uses
core/models.py, services/ (future)
```

## Technology Stack

- **Language**: Python 3.10+
- **Package Manager**: uv
- **Web Framework**: FastAPI
- **Database**: PostgreSQL (SQLAlchemy + psycopg2-binary)
- **Migrations**: Alembic
- **Logging**: Loguru
- **Configuration**: Pydantic Settings
- **Message Queue**: RabbitMQ (Phase 0 setup only)
- **Storage**: MinIO (Phase 0 setup only)

## Directory Structure

```text
analytics_engine/
├── cmd/                        # Entry Points
│   ├── analytics_api/
│   │   └── main.py            # API entry: loads config, starts FastAPI
│   └── analytics_consumer/
│       └── main.py            # Consumer entry: loads config, starts consumer
├── internal/                   # Internal Implementation
│   ├── api/
│   │   └── main.py            # Registers FastAPI routes
│   └── consumers/
│       └── main.py            # Registers message consumers
├── core/                       # Shared Core
│   ├── config.py              # Settings (Pydantic)
│   ├── models.py              # Database models (SQLAlchemy)
│   ├── logger.py              # Logging setup (Loguru)
│   └── ...
├── services/                   # Business Logic (future)
├── migrations/                 # Alembic migrations
│   └── env.py                 # Uses core.models and core.config
├── pyproject.toml             # uv configuration
├── docker-compose.dev.yml     # Dev environment
└── Makefile                   # Common command
```
