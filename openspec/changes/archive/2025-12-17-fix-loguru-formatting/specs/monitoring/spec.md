## MODIFIED Requirements

### Requirement: Structured Logging

The system SHALL use Loguru for structured logging with proper string formatting.

#### Scenario: Logger uses f-string or format-style interpolation

- **WHEN** a log message contains dynamic values
- **THEN** the system SHALL use f-string (`f"message {value}"`) or Loguru's format-style (`"message {}", value`) instead of printf-style (`"message %s", value`)

#### Scenario: Log output displays actual values

- **WHEN** a log message is written with dynamic values
- **THEN** the log output SHALL display the actual interpolated values, not format placeholders like `%s` or `%d`

#### Scenario: Logger configuration is documented

- **WHEN** a developer needs to add logging to a new module
- **THEN** the system SHALL provide clear documentation in `core/logger.py` and `document/logging-guide.md` explaining:
  - Correct Loguru formatting syntax
  - Log level guidelines
  - File rotation and retention policies
  - Examples of common logging patterns
