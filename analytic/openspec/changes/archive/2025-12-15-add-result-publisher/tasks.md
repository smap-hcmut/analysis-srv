# Implementation Tasks

## 1. Infrastructure Setup

- [x] 1.1 Create message types in `models/messages.py`

  - Define `AnalyzeResultMessage`, `AnalyzeResultPayload`, `AnalyzeItem`, `AnalyzeError` dataclasses
  - Add JSON serialization support
  - Validates: Requirement "Result Message Format"

- [x] 1.2 Add config settings in `core/config.py`

  - Add `publish_exchange`, `publish_routing_key`, `publish_enabled` settings
  - Validates: Requirement "Publisher Configuration"

- [x] 1.3 Create RabbitMQ publisher in `infrastructure/messaging/publisher.py`
  - Implement `RabbitMQPublisher` class
  - Add `setup()` method for exchange declaration
  - Add `publish_analyze_result()` method
  - Validates: Requirement "Result Publishing"

## 2. Consumer Integration

- [x] 2.1 Update `internal/consumers/main.py` to build result messages

  - Add `build_result_items()` helper function
  - Add `build_error_items()` helper function
  - Integrate result message building into `process_event_format()`
  - Validates: Requirement "Batch Result Aggregation"

- [x] 2.2 Update `internal/consumers/main.py` to publish results

  - Accept publisher as parameter in `create_message_handler()`
  - Call `publisher.publish_analyze_result()` after batch processing
  - Handle MinIO fetch errors with error result publishing
  - Validates: Requirement "Result Publishing"

- [x] 2.3 Update `command/consumer/main.py` entry point
  - Initialize `RabbitMQPublisher` with shared channel
  - Call `publisher.setup()` before consuming
  - Pass publisher to message handler factory
  - Validates: Requirement "Publisher Lifecycle"

## 3. Error Handling

- [x] 3.1 Implement MinIO fetch error handling

  - Publish error result when MinIO fetch fails
  - Include batch-level error in errors array
  - Validates: Requirement "Error Result Publishing"
  - Implementation: `_publish_error_result()` in `internal/consumers/main.py`

- [x] 3.2 Implement publish failure handling
  - Log error on publish failure
  - Continue processing (don't block consumer)
  - Validates: Requirement "Publish Failure Handling"
  - Implementation: try/except in `_publish_batch_result()` and `_publish_error_result()`

## 4. Testing

- [x] 4.1 Add unit tests for message types

  - Test dataclass serialization
  - Test field validation
  - Location: `tests/test_models/test_messages.py`
  - Result: 19 tests passed

- [x] 4.2 Add unit tests for publisher

  - Test exchange declaration
  - Test message publishing
  - Test error handling
  - Location: `tests/test_messaging/test_publisher.py`
  - Result: 14 tests passed

- [x] 4.3 Add integration tests for consumer with publisher
  - Test helper functions: `build_result_items()`, `build_error_items()`
  - Test handler creation with/without publisher
  - Test error scenarios
  - Location: `tests/test_consumers/test_result_publishing.py`
  - Result: 16 tests passed

## 5. Documentation

- [x] 5.1 Update README with publisher configuration
  - Added Result Publishing section with output message schema
  - Added PUBLISH_EXCHANGE, PUBLISH_ROUTING_KEY, PUBLISH_ENABLED to configuration
  - Added link to integration-analytics-service.md in Documentation section
- [x] 5.2 Update `document/integration-analytics-service.md` checklist
  - Marked all Analytics Service tasks as complete
  - Added implementation details with file paths and test results
- [x] 5.3 Sync config with `.env.example`
  - Added Result Publishing Configuration section
  - Added PUBLISH_EXCHANGE, PUBLISH_ROUTING_KEY, PUBLISH_ENABLED variables
- [x] 5.4 Update manifest files (`docker-compose.yml`)
  - Added publisher environment variables to consumer service
- [x] 5.5 Update current doc behavior
  - Renamed "Crawler Event Integration Configuration (NEW)" to "(Input)"
  - Added "(Output)" section for Result Publishing
- [x] 5.6 Update `document/analytics-behavior.md`
  - Added Result Publishing section with message schema, types, and flow
  - Updated architecture diagram to include Collector Service
  - Updated data flow to include publish step
  - Added publisher configuration to environment variables
  - Added link to integration-analytics-service.md
- [x] 5.7 Update k8s manifests (`k8s/configmap.yaml`)
  - Added PUBLISH_EXCHANGE, PUBLISH_ROUTING_KEY, PUBLISH_ENABLED to ConfigMap

## Dependencies

- Task 1.1 → 2.1 (message types needed for building results)
- Task 1.2 → 2.3 (config needed for publisher setup)
- Task 1.3 → 2.2, 2.3 (publisher needed for integration)
- Task 2.1 → 2.2 (helpers needed for publishing)

## Parallelizable Work

- Tasks 1.1, 1.2, 1.3 can be done in parallel
- Tasks 4.1, 4.2 can be done in parallel after their dependencies
