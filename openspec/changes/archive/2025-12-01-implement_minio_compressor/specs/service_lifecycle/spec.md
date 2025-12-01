# service_lifecycle Specification

## MODIFIED Requirements

### Requirement: Consumer Service Model Initialization

The Analytics Engine Consumer service SHALL initialize AI model instances during startup before processing messages, and SHALL handle decompressed JSON data from MinIO.

**Rationale**: Consumer service processes messages asynchronously and needs AI models available throughout its lifecycle. Additionally, consumer must handle compressed MinIO files by automatically decompressing them before JSON parsing.

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

