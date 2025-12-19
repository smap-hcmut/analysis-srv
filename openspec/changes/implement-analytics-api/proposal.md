# Change: Implement Analytics API Service

## Why

Dashboard frontend cần REST API để truy xuất dữ liệu phân tích đã xử lý. Hiện tại Analytics Engine chỉ có consumer service, chưa có API layer để serve data cho clients.

## What Changes

- Thêm Analytics API Service với FastAPI framework
- Implement 8 REST endpoints theo API design proposal
- Tạo command/api entry point và internal/api implementation
- Thêm database repository layer cho data access
- Implement standardized response format và error handling
- Setup Swagger UI documentation
- Thêm comprehensive filtering, pagination, và sorting

## Impact

- Affected specs: Thêm mới `analytics_api` capability
- Affected code:
  - Tạo mới: `command/api/`, `internal/api/`, `repository/`
  - Cập nhật: `models/` (thêm Pydantic schemas), `core/` (API config)
  - Dependencies: FastAPI, Uvicorn, SQLAlchemy async
- Infrastructure: PostgreSQL database (sử dụng existing tables)
- Performance: Read-only operations, optimized with database indexes