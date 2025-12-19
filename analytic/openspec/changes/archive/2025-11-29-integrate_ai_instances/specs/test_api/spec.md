# Test API Capability

**Capability**: `test_api`  
**Owner**: Analytics Engine Team  
**Status**: Proposed

---

## ADDED Requirements

### Requirement: Test Analytics Endpoint

The Analytics Engine SHALL provide a test endpoint `/api/v1/test/analytics` for validating JSON input format and AI model integration.

**Rationale**: Developers need a way to test the analytics pipeline with real JSON data matching the master-proposal.md format. This endpoint serves as both a development tool and living documentation of expected input/output.

#### Scenario: Accept Valid JSON Input

**Given** the test endpoint is available  
**When** a POST request is sent to `/api/v1/test/analytics` with valid JSON matching master-proposal.md format  
**Then** the request SHALL be accepted (HTTP 200)  
**And** the JSON SHALL be validated against the schema  
**And** the response SHALL include the post_id from input

#### Scenario: Reject Invalid JSON Input

**Given** the test endpoint is available  
**When** a POST request is sent with invalid JSON (missing required fields)  
**Then** the request SHALL be rejected (HTTP 422)  
**And** the error response SHALL indicate which fields are invalid

---

### Requirement: Full Analytics Debug Response

The test endpoint SHALL return a comprehensive debug response showing all analytics pipeline stages.

**Rationale**: For development and debugging, developers need visibility into each processing stage to validate correctness.

#### Scenario: Return Full Debug Response

**Given** a valid JSON input is processed  
**When** the test endpoint generates a response  
**Then** the response SHALL include a `preprocessing` section  
**And** the response SHALL include a `keywords` section  
**And** the response SHALL include a `sentiment` section  
**And** the response SHALL include a `metadata` section  
**And** each section SHALL indicate model availability status

---

### Requirement: Model Availability Validation

The test endpoint SHALL validate that AI models are properly initialized and accessible.

**Rationale**: The test endpoint should confirm that dependency injection is working correctly.

#### Scenario: Models Available

**Given** PhoBERT and SpaCy-YAKE are initialized  
**When** the test endpoint is called  
**Then** the response SHALL indicate `phobert_available: true`  
**And** the response SHALL indicate `spacyyake_available: true`  
**And** the response SHALL indicate `models_initialized: true`

#### Scenario: Models Not Available

**Given** models failed to initialize  
**When** the test endpoint is called  
**Then** the endpoint SHALL return HTTP 500  
**And** the error message SHALL indicate which models are unavailable

---

### Requirement: Performance Requirements

The test endpoint SHALL meet performance requirements suitable for development testing.

**Rationale**: While this is a test endpoint, it should still be reasonably fast to provide good developer experience.

#### Scenario: Response Time

**Given** a valid JSON input  
**When** the test endpoint processes the request  
**Then** the response SHALL be returned within 1 second  
**And** the response time SHALL be logged

---

### Requirement: API Documentation

The test endpoint SHALL be automatically documented in OpenAPI/Swagger UI.

**Rationale**: Developers should be able to discover and test the endpoint via Swagger UI.

#### Scenario: Swagger UI Documentation

**Given** the API service is running  
**When** a developer accesses `/docs` (Swagger UI)  
**Then** the test endpoint SHALL be visible  
**And** the request schema SHALL be documented  
**And** the response schema SHALL be documented  
**And** developers SHALL be able to test the endpoint directly from Swagger UI
