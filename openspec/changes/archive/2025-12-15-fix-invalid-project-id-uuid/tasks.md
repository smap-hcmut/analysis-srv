# Implementation Tasks

## 1. UUID Utility Module

- [x] 1.1 Create `utils/uuid_utils.py` with `extract_uuid()` function
- [x] 1.2 Add `is_valid_uuid()` function
- [x] 1.3 Write unit tests for UUID utilities

## 2. Repository Layer Sanitization

- [x] 2.1 Import UUID utilities in `repository/analytics_repository.py`
- [x] 2.2 Add `project_id` sanitization logic in `save()` method
- [x] 2.3 Add warning log when sanitizing invalid `project_id`
- [x] 2.4 Write unit tests for repository sanitization

## 3. Verification

- [x] 3.1 Run existing tests to ensure no regression
- [x] 3.2 Test with sample invalid `project_id` values
- [x] 3.3 Verify SQL queries work with sanitized UUIDs
