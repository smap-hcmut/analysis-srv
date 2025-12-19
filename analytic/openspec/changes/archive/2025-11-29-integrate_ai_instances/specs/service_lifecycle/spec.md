# Service Lifecycle Capability

**Capability**: `service_lifecycle`  
**Owner**: Analytics Engine Team  
**Status**: Proposed

---

## ADDED Requirements

### Requirement: AI Model Initialization

The Analytics Engine API service SHALL initialize AI model instances during application startup using FastAPI lifespan context manager.

**Rationale**: AI models (PhoBERT ONNX, SpaCy-YAKE) are expensive to load (~2-5 seconds). Loading them once during startup and reusing across requests provides significant performance benefits compared to loading per-request.

#### Scenario: Successful Model Loading

**Given** the API service is starting up  
**When** the lifespan context manager executes  
**Then** PhoBERT ONNX model SHALL be initialized successfully  
**And** SpaCy-YAKE model SHALL be initialized successfully  
**And** both models SHALL be stored in `app.state` for dependency injection  
**And** startup SHALL complete within 10 seconds  
**And** initialization events SHALL be logged

#### Scenario: Model Loading Failure

**Given** the API service is starting up  
**When** a model fails to initialize (e.g., missing files, OOM)  
**Then** the error SHALL be logged with details  
**And** the application SHALL fail to start (raise exception)  
**And** a clear error message SHALL indicate which model failed

---

### Requirement: Model Cleanup on Shutdown

The Analytics Engine API service SHALL properly clean up AI model instances during application shutdown.

**Rationale**: Proper resource cleanup prevents memory leaks and ensures graceful shutdown.

#### Scenario: Graceful Shutdown

**Given** the API service is running with models loaded  
**When** a shutdown signal is received  
**Then** model instances SHALL be deleted from `app.state`  
**And** shutdown events SHALL be logged  
**And** shutdown SHALL complete within 5 seconds

---

### Requirement: Dependency Injection for Models

The Analytics Engine SHALL provide dependency injection functions to access AI model instances in API endpoints.

**Rationale**: Dependency injection enables testability (easy to mock models) and follows FastAPI best practices.

#### Scenario: Inject PhoBERT Model

**Given** the API service has initialized PhoBERT  
**When** an endpoint uses `get_phobert()` dependency  
**Then** the endpoint SHALL receive the PhoBERT instance  
**And** the instance SHALL be the same object across all requests (singleton)

#### Scenario: Inject SpaCy-YAKE Model

**Given** the API service has initialized SpaCy-YAKE  
**When** an endpoint uses `get_spacyyake()` dependency  
**Then** the endpoint SHALL receive the SpaCy-YAKE instance  
**And** the instance SHALL be the same object across all requests (singleton)

#### Scenario: Model Not Initialized

**Given** the API service failed to initialize models  
**When** an endpoint tries to use a model dependency  
**Then** an appropriate error SHALL be raised  
**And** the error message SHALL indicate the model is not available

---

### Requirement: Consumer Service Model Initialization

The Analytics Engine Consumer service SHALL initialize AI model instances during startup before processing messages.

**Rationale**: Consumer service processes messages asynchronously and needs AI models available throughout its lifecycle. Loading models once at startup ensures consistent performance.

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
