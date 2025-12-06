# service_lifecycle Specification

## Purpose
TBD - created by archiving change integrate_ai_instances. Update Purpose after archive.
## Requirements
### Requirement: Consumer Service Model Initialization

The Analytics Engine Consumer service SHALL initialize AI model instances during startup before processing messages, and SHALL handle decompressed JSON data from MinIO.

**Rationale**: Consumer service processes messages asynchronously and needs AI models available throughout its lifecycle. This is now the ONLY service entry point for Analytics Engine.

#### Scenario: Successful Consumer Model Loading

**Given** the Consumer service is starting up  
**When** the main function executes  
**Then** PhoBERT ONNX model SHALL be initialized successfully  
**And** SpaCy-YAKE model SHALL be initialized successfully  
**And** RabbitMQClient SHALL be initialized and connected  
**And** message consumption SHALL start using the client  
**And** startup SHALL complete within 10 seconds  
**And** initialization events SHALL be logged

#### Scenario: Consumer Initialization Failure

**Given** the Consumer service is starting up  
**When** a model fails to initialize OR RabbitMQ connection fails  
**Then** the error SHALL be logged with details  
**And** the application SHALL fail to start (raise exception)  
**And** a clear error message SHALL indicate the cause

#### Scenario: Consumer Graceful Shutdown

**Given** the Consumer service is running  
**When** a shutdown signal is received  
**Then** RabbitMQ connection SHALL be closed gracefully  
**And** model instances SHALL be deleted  
**And** shutdown events SHALL be logged  
**And** shutdown SHALL complete within 5 seconds

#### Scenario: Consumer Processes Compressed MinIO Data

**Given** the Consumer service is running  
**When** a message contains a MinIO reference to a compressed file  
**Then** the system SHALL download the file from MinIO  
**And** the system SHALL detect compression from metadata  
**And** the system SHALL automatically decompress the data  
**And** the system SHALL parse JSON from decompressed data  
**And** the system SHALL process the post data through the orchestrator

#### Scenario: Consumer Processes Uncompressed MinIO Data

**Given** the Consumer service is running  
**When** a message contains a MinIO reference to an uncompressed file  
**Then** the system SHALL download the file from MinIO  
**And** the system SHALL detect no compression metadata  
**And** the system SHALL parse JSON directly without decompression  
**And** the system SHALL process the post data through the orchestrator  
**And** backward compatibility SHALL be maintained

#### Scenario: Consumer Handles Decompression Failure

**Given** the Consumer service is running  
**When** a message contains a MinIO reference with invalid compression  
**Then** the system SHALL log a clear error message  
**And** the message SHALL be rejected (nacked)  
**And** the error SHALL indicate decompression failure

#### Scenario: Consumer is Single Entry Point

**Given** the Analytics Engine is deployed  
**When** external systems need to process analytics  
**Then** they SHALL publish events to RabbitMQ `smap.events` exchange  
**And** the Consumer service SHALL be the only entry point  
**And** no HTTP API SHALL be available for direct processing

### Requirement: Consumer service startup with event-driven configuration

The consumer service SHALL initialize and connect to RabbitMQ using event-driven mode configuration without requiring feature flags. The consumer MUST NOT reference undefined feature flags (`new_mode_enabled`, `legacy_mode_enabled`). Configuration MUST be explicit and fail-fast if settings are missing.

**Rationale:** Event-driven architecture is the standard mode. Feature flags for dual-mode operation have been removed to simplify configuration and prevent errors from undefined settings.

#### Scenario: Consumer starts with event-driven configuration

**Given:**

- Settings contain `event_queue_name`, `event_exchange`, `event_routing_key`
- RabbitMQ is accessible

**When:**

- Consumer service starts via `python -m command.consumer.main`

**Then:**

- Consumer binds to `smap.events` exchange with routing key `data.collected`
- Queue `analytics.data.collected` is declared
- No AttributeError is raised for undefined settings
- Log shows "Using event-driven mode: exchange=smap.events, routing_key=data.collected"

**Acceptance:**

```python
# command/consumer/main.py
queue_name = settings.event_queue_name  # Direct access, no conditional
exchange_name = settings.event_exchange
routing_key = settings.event_routing_key

await rabbitmq_client.connect(
    exchange_name=exchange_name,
    routing_key=routing_key,
)
```

---

### Requirement: Configuration validation for event-driven settings

Configuration validation MUST verify that all required event-driven settings are present. The validator SHALL check for `event_queue_name`, `event_exchange`, and `event_routing_key`. Feature flag validation logic MUST be removed.

**Rationale:** Configuration validation should focus on actual required settings rather than feature flags that no longer exist.

#### Scenario: Configuration validation passes for event-driven mode

**Given:**

- Config contains `event_queue_name = "analytics.data.collected"`
- Config contains `event_exchange = "smap.events"`
- Config contains `event_routing_key = "data.collected"`

**When:**

- ConfigValidator runs validation

**Then:**

- Validation passes without feature flag checks
- No warnings about "legacy mode" or "new mode"
- No AttributeError for undefined settings

**Acceptance:**

```python
# core/config_validation.py - REMOVED SECTION
# Lines 258-276 should be deleted (feature flag validation)

# Validation focuses on actual settings
if not settings.event_queue_name:
    errors.append("event_queue_name is required")
if not settings.event_exchange:
    errors.append("event_exchange is required")
```

