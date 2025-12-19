# Implementation Tasks

## 1. Fix ID Precision Loss (P0)

- [x] 1.1 Update PostAnalytics model to use String type for ID serialization

  - Ensure ID is serialized as string in JSON responses
  - Add custom JSON encoder for BigInt values
  - _Requirements: event_consumption, crawler_metadata_
  - **Done**: Created `utils/json_encoder.py` with `BigIntEncoder` and `serialize_analytics_result`

- [x] 1.2 Add ID validation utility
  - Create utility to validate TikTok ID format
  - Log warning when ID appears truncated
  - _Requirements: event_consumption_
  - **Done**: Created `utils/id_utils.py` with `validate_tiktok_id`, `detect_truncated_id`, `log_id_warnings`
  - **Done**: Updated `internal/consumers/item_processor.py` to use ID validation

## 2. Fix SentimentAnalyzer Configuration (P0)

- [x] 2.1 Add SentimentAnalyzer initialization validation

  - Verify PhoBERT model is loaded on startup
  - Add explicit error logging when model not configured
  - _Requirements: monitoring_
  - **Done**: Updated `command/consumer/main.py` with detailed health check logging
  - **Done**: Added AI Model Health Check Summary on startup

- [x] 2.2 Fix orchestrator to properly inject SentimentAnalyzer
  - Ensure SentimentAnalyzer is passed to orchestrator
  - Add startup health check for sentiment module
  - _Requirements: monitoring_
  - **Done**: Fixed `internal/consumers/main.py` - `create_message_handler` now creates SentimentAnalyzer from PhoBERT
  - **Done**: Fixed `process_single_item` to accept and use `sentiment_analyzer` parameter
  - **Done**: Orchestrator now receives proper SentimentAnalyzer instance instead of `None`

## 3. Fix Metadata Extraction (P1)

- [x] 3.1 Debug and fix crawler metadata extraction

  - Add detailed logging for event payload structure
  - Fix job_id, batch_index, task_type extraction
  - _Requirements: crawler_metadata_
  - **Done**: Updated `parse_event_metadata()` with detailed logging and missing field warnings
  - **Done**: Updated `enrich_with_batch_context()` with debug logging for enriched metadata

- [x] 3.2 Fix keyword_source and crawled_at extraction
  - Ensure keyword_source is extracted from correct field
  - Fix crawled_at timestamp parsing
  - _Requirements: crawler_metadata_
  - **Done**: Added `_extract_crawler_metadata()` method to orchestrator
  - **Done**: Updated `_build_final_result()` and `_build_skipped_result()` to include crawler metadata
  - **Done**: Fixed crawled_at timestamp parsing with proper error handling

## 4. Fix Data Serialization (P1)

- [x] 4.1 Fix NULL value handling

  - Ensure None values are serialized as JSON null
  - Add sanitization for "NULL" string values
  - _Requirements: crawler_metadata_
  - **Done**: Added `sanitize_null_string()` function to convert "NULL" strings to Python None
  - **Done**: Added `sanitize_analytics_data()` function to sanitize all nullable fields

- [x] 4.2 Fix boolean serialization
  - Ensure boolean values are serialized as JSON true/false
  - Add validation for boolean fields
  - _Requirements: crawler_metadata_
  - **Done**: Added `sanitize_boolean()` function to convert string "True"/"False" to Python bool
  - **Done**: Updated `repository/analytics_repository.py` to call `sanitize_analytics_data()` before save

## 5. Add Debug Monitoring (User Request)

- [x] 5.1 Add detailed data extraction logging

  - Log raw event payload structure on receive
  - Log extracted metadata fields before processing
  - Log final analytics payload before save
  - _Requirements: monitoring_
  - **Done**: Created `utils/debug_logging.py` with debug logging utilities
  - **Done**: Added `DEBUG_RAW_DATA` env var support ("true", "sample", "false")
  - **Done**: Integrated debug logging into `internal/consumers/main.py`

- [x] 5.2 Add data quality validation checks
  - Validate required fields are present
  - Log warnings for missing/invalid data
  - _Requirements: monitoring_
  - **Done**: Added `log_data_quality_metrics()` to track metadata completeness
  - **Done**: Added tracking for items with full metadata, sentiment analysis, and truncated IDs
  - **Done**: Added warning when metadata completeness drops below 80%

## 6. Testing

- [x] 6.1 Add unit tests for ID serialization

  - Test BigInt ID handling
  - Test string serialization
  - _Requirements: event_consumption_
  - **Done**: Created `tests/test_utils/test_id_utils.py` with 25 tests
  - **Done**: Tests cover ensure_string_id, is_bigint_id, detect_truncated_id, validate_tiktok_id

- [x] 6.2 Add unit tests for data sanitization
  - Test NULL string handling
  - Test boolean string handling
  - _Requirements: crawler_metadata_
  - **Done**: Created `tests/test_utils/test_json_encoder.py` with 29 tests
  - **Done**: Tests cover sanitize_null_string, sanitize_boolean, sanitize_analytics_data, BigIntEncoder
  - **Done**: All 54 tests passing
