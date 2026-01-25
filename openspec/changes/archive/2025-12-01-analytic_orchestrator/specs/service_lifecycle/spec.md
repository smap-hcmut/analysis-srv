## ADDED Requirements

### Requirement: Single-Post Analytics Orchestrator

The system SHALL provide an `AnalyticsOrchestrator` component responsible for
processing a **single Atomic JSON post** through the full analytics pipeline
(Modules 1–5) and persisting the enriched result.

#### Scenario: End-to-end orchestration for one post
- **Given** an Atomic JSON post with `meta`, `content`, `interaction`, `author`,
  and optional `comments`
- **When** the orchestrator processes the post
- **Then** the system SHALL:
  - Run the following modules in order: Preprocessor → Intent → Keyword →
    Sentiment → Impact
  - Apply skip logic for SPAM/SEEDING/noise based on preprocessor stats and
    intent classification
  - Produce a result object compatible with the `post_analytics` schema and
    master proposal output examples

### Requirement: Dual Entry Points (Queue + Dev API)

The system SHALL expose two primary entry points for orchestrated analytics:
one for production queue-based processing and one for direct JSON dev/testing.

#### Scenario: Queue-based processing from MinIO
- **Given** a RabbitMQ message containing a reference to a MinIO object
  (`bucket`, `path`) for a post JSON
- **When** the consumer entry point handles the message
- **Then** the system SHALL:
  - Download the JSON via a MinIO adapter
  - Delegate the resulting `post_data` dict to `AnalyticsOrchestrator`
  - Persist the orchestrator’s output into `post_analytics`
  - Ack or nack the message based on success or failure

#### Scenario: Dev/test API for direct JSON input
- **Given** a developer calls a dev/test API endpoint with a full Atomic JSON
  post in the request body
- **When** the endpoint invokes the orchestrator
- **Then** the system SHALL:
  - Run the same orchestration steps as the queue-based flow
  - Return the final analytics payload in the HTTP response body
  - Optionally persist the result, consistent with the production flow

### Requirement: Skip Logic for Noise & Spam

The orchestrator SHALL implement skip logic to avoid running expensive AI
modules for posts that are clearly noise (spam, seeding, or too short).

#### Scenario: Skip spam/seeding posts
- **Given** a post whose preprocessor stats and intent classification indicate
  SPAM or SEEDING
- **When** the orchestrator processes the post
- **Then** the system SHALL:
  - Skip keyword, sentiment, and impact modules
  - Persist a record with neutral defaults (e.g., NEUTRAL sentiment, LOW risk)
  - Record the primary intent (SEEDING/SPAM) and a skip reason

#### Scenario: Process valid posts fully
- **Given** a post that is not classified as spam or seeding and whose
  preprocessor stats do not signal noise
- **When** the orchestrator processes the post
- **Then** the system SHALL:
  - Run all 5 modules (Preprocessor → Intent → Keyword → Sentiment → Impact)
  - Persist the full analytics details, including aspects and impact metrics


