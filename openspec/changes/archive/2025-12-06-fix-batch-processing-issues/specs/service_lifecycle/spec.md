# Capability: service_lifecycle

## ADDED Requirements

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

