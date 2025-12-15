# Change: Add Result Publisher for Collector Integration

## Why

Analytics Engine hiện tại chỉ consume events từ Crawler và lưu kết quả vào database, nhưng **không publish kết quả phân tích về Collector service**. Điều này khiến Collector không thể:

- Track tiến độ phân tích (analyze_done, analyze_errors)
- Notify webhook về completion status
- Cập nhật project state

Theo integration contract trong `document/integration-analytics-service.md`, Analytics cần publish `analyze.result` message về exchange `results.inbound` để Collector có thể xử lý batch results.

## What Changes

- **ADDED**: RabbitMQ Publisher infrastructure (`infrastructure/messaging/publisher.py`)
- **ADDED**: Message types cho analyze result (`models/messages.py`)
- **ADDED**: Config settings cho publish exchange/routing key
- **MODIFIED**: Consumer flow để publish kết quả sau khi process batch
- **MODIFIED**: Entry point để khởi tạo publisher

## Impact

- Affected specs: `event_consumption`, `batch_processing` (new capability: `result_publishing`)
- Affected code:
  - `infrastructure/messaging/publisher.py` (new)
  - `models/messages.py` (new)
  - `core/config.py` (add publish settings)
  - `internal/consumers/main.py` (integrate publisher)
  - `command/consumer/main.py` (initialize publisher)

## Dependencies

- RabbitMQ exchange `results.inbound` must exist (created by Collector service)
- Collector service must be ready to consume `analyze.result` messages

## Risks

- **Message delivery failure**: Mitigated by using durable exchange and persistent messages
- **Schema mismatch**: Mitigated by following exact contract from integration doc
