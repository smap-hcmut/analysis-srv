# Change: Fix Production Data Quality Issues

## Why

Phân tích dữ liệu production từ Analytics Service (2025-12-15) phát hiện nhiều vấn đề nghiêm trọng về data quality:

1. **ID precision loss (P0)**: TikTok post ID 19 chữ số bị làm tròn khi serialize JSON
2. **SentimentAnalyzer disabled (P0)**: Module sentiment không hoạt động, tất cả posts trả về NEUTRAL
3. **Metadata missing (P1)**: Crawler metadata (job_id, batch_index, keyword_source...) đều là NULL
4. **NULL as string (P1)**: NULL values được lưu dưới dạng string "NULL" thay vì JSON null
5. **Boolean as string (P2)**: Boolean được lưu dưới dạng string "True"/"False"

## What Changes

### Data Serialization Fixes

- **BREAKING**: Thay đổi ID serialization từ number sang string trong JSON response
- Fix NULL value handling trong serialization layer
- Fix boolean serialization để output đúng JSON boolean

### Metadata Extraction Fixes

- Fix crawler metadata extraction từ event payload
- Ensure job_id, batch_index, task_type, keyword_source được populate đúng

### Monitoring & Debug

- Add detailed logging cho data extraction từ crawler events
- Add data quality validation checks
- Add debug endpoint/logging để monitor raw data từ crawler

### SentimentAnalyzer Configuration

- Verify và fix SentimentAnalyzer initialization
- Add configuration validation on startup

## Impact

- Affected specs: `event_consumption`, `crawler_metadata`, `monitoring`
- Affected code:
  - `repository/analytics_repository.py` - Data persistence
  - `services/analytics/orchestrator.py` - Pipeline orchestration
  - `internal/consumers/item_processor.py` - Message processing
  - `internal/consumers/main.py` - Consumer initialization
  - `models/database.py` - Data models
