## ADDED Requirements

### Requirement: Project ID UUID Validation

The system SHALL validate and sanitize `project_id` field to ensure it contains a valid UUID before database operations.

#### Scenario: Valid UUID passes through

- **WHEN** `project_id` is a valid UUID format (e.g., `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`)
- **THEN** use the value as-is without modification

#### Scenario: Extract UUID from invalid format

- **WHEN** `project_id` contains a valid UUID with extra suffix (e.g., `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor"`)
- **THEN** extract the valid UUID portion (`"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`)
- **AND** log a warning with original and sanitized values

#### Scenario: Reject completely invalid project_id

- **WHEN** `project_id` does not contain any valid UUID pattern (e.g., `"invalid-string"`)
- **THEN** raise ValueError with descriptive message

#### Scenario: Handle empty project_id

- **WHEN** `project_id` is empty string or None
- **THEN** raise ValueError indicating project_id is required

---

### Requirement: UUID Utility Functions

The system SHALL provide utility functions for UUID validation and extraction in `utils/uuid_utils.py`.

#### Scenario: Extract UUID from string

- **WHEN** calling `extract_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")`
- **THEN** return `"fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"`

#### Scenario: Extract UUID returns None for invalid

- **WHEN** calling `extract_uuid("invalid-string")`
- **THEN** return `None`

#### Scenario: Validate UUID format

- **WHEN** calling `is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80")`
- **THEN** return `True`

#### Scenario: Validate UUID rejects invalid

- **WHEN** calling `is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")`
- **THEN** return `False`
