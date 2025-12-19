# Change: Remove API Service

## Why

Analytics Service theo kiến trúc event-driven chỉ cần consumer service để consume `data.collected` events từ RabbitMQ. API service hiện tại là boilerplate code không cần thiết, tạo thêm complexity và maintenance burden.

## What Changes

- **REMOVE** `command/api/` - API entry point
- **REMOVE** `internal/api/` - API implementation (routes, dependencies)
- **REMOVE** API-specific tests (`test_api_swagger.py`, `test_api_integration.py`)
- **REMOVE** `run-api` command từ Makefile
- **REMOVE** API settings từ `core/config.py` (`api_host`, `api_port`, `api_reload`)
- **BREAKING** `make run-api` command sẽ không còn hoạt động
- **BREAKING** API endpoints (`/dev/process-post-direct`, `/test/analytics`) không còn available

## Impact

- Affected specs: `test_api`, `service_lifecycle`
- Affected code: `command/api/`, `internal/api/`, `core/config.py`, `Makefile`
- Documentation: `document/architecture.md`, `document/analytic_orchestrator.md`, `openspec/project.md`
