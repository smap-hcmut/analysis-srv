# Implementation Tasks

## 1. Update Logger Configuration and Documentation

- [x] 1.1 Update `core/logger.py` với docstring và examples về cách sử dụng đúng Loguru
- [x] 1.2 Create `document/logging-guide.md` với hướng dẫn chi tiết

## 2. Fix Logger Calls in Infrastructure Layer

- [x] 2.1 Fix `infrastructure/messaging/publisher.py` - 7 calls fixed
- [x] 2.2 Fix `infrastructure/storage/minio_client.py` - 4 calls fixed

## 3. Fix Logger Calls in Services Layer

- [x] 3.1 Fix `services/analytics/orchestrator.py` - 6 calls fixed

## 4. Fix Logger Calls in Internal Consumers

- [x] 4.1 Fix `internal/consumers/main.py` - 20 calls fixed
- [x] 4.2 Fix `internal/consumers/item_processor.py` - 4 calls fixed

## 5. Fix Logger Calls in Repository Layer

- [x] 5.1 Fix `repository/analytics_repository.py` - 5 calls fixed
- [x] 5.2 Fix `repository/crawl_error_repository.py` - 4 calls fixed

## 6. Fix Logger Calls in Utils and Core

- [x] 6.1 Fix `utils/debug_logging.py` - 6 calls fixed
- [x] 6.2 Fix `core/config_validation.py` - 5 calls fixed
- [x] 6.3 Fix `command/consumer/main.py` - 5 calls fixed

## 7. Verification

- [x] 7.1 Run existing tests to ensure no regressions (522 passed)
- [x] 7.2 Syntax validation passed for all modified files
