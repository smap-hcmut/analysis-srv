## Change: Implement Analytics Orchestrator & Entry Points

**Change ID**: `analytic_orchestrator`  
**Status**: Proposal  
**Related Docs**:
- `analytic_orchestrator.md`
- `documents/implement_plan.md`
- `documents/master-proposal.md`

## Why

The Analytics Engine already implements the core processing modules:
- Module 1: `TextPreprocessor`
- Module 2: `IntentClassifier`
- Module 3: `KeywordExtractor`
- Module 4: `SentimentAnalyzer`
- Module 5: `ImpactCalculator`

However, the system still lacks a **single, cohesive orchestration layer** that:
- Accepts **Atomic JSON** posts (from MinIO or directly via API).
- Runs the 5-stage pipeline **sequentially and consistently**.
- Applies **gatekeeping rules** (skip spam/seeding/noise before expensive AI).
- Persists enriched analytics into `post_analytics` with the full output contract
  defined in `documents/master-proposal.md`.
- Exposes **clear entry points** for:
  - Production queue-based processing (RabbitMQ + MinIO).
  - Developer-friendly API for direct JSON testing (no MinIO/queue).

Without this orchestrator:
- Each entry point has to re-implement ad-hoc glue logic between modules.
- There is no single place to enforce cross-cutting rules (skip logic, metrics, error handling).
- The implementation plan in `documents/implement_plan.md` (Phase 1) and the
  architecture in `documents/master-proposal.md` (Section 3 Service Architecture)
  remain partially theoretical.

This change introduces a **first-class `AnalyticsOrchestrator`** and entry points to:
- Close the loop from MinIO → Processing Pipeline → PostgreSQL.
- Make it trivial for developers to exercise the full pipeline over sample JSON.

## What Changes

- **New core orchestrator**:
  - Implement `AnalyticsOrchestrator` in `services/analytics/orchestrator.py` that:
    - Accepts a single **Atomic Post JSON** dict (`post_data`).
    - Runs Modules 1–5 in order:
      1. `TextPreprocessor` → `clean_text` + stats.
      2. `IntentClassifier` → primary intent + `should_skip`.
      3. `KeywordExtractor` → aspect-labelled keywords.
      4. `SentimentAnalyzer` → overall + aspect-based sentiment (ABSA).
      5. `ImpactCalculator` → impact score, risk level, viral/KOL flags.
    - Implements skip logic:
      - Use preprocessor stats and intent signals to short-circuit SPAM/SEEDING.
    - Constructs a final analytics payload compatible with `PostAnalytics` and
      the output contract in `master-proposal.md`.
    - Persists results via a dedicated repository abstraction.

- **MinIO storage adapter**:
  - Implement a small `MinioAdapter` in `infrastructure/storage/minio_client.py` that:
    - Reads JSON objects from MinIO based on `bucket` + `object_path`.
    - Streams content and parses into Python dicts without temporary files.

- **Entry point: RabbitMQ consumer (production flow)**:
  - Implement a queue-based entry point (e.g. `commands/consumer/orchestrated_main.py` or
    extend `internal/consumers/main.py`) that:
    - Receives messages containing `data_ref` (bucket/path).
    - Uses `MinioAdapter` to fetch the Atomic JSON.
    - Delegates the `post_data` to `AnalyticsOrchestrator.process_post`.
    - Acks/Nacks messages based on success/failure.

- **Entry point: Dev/Test API endpoint**:
  - Add a dev/test-only FastAPI endpoint (e.g. under `internal/api/routes/test.py`) that:
    - Accepts an entire Atomic JSON payload in the request body.
    - Delegates to `AnalyticsOrchestrator` and returns the enriched analytics result.
    - Does not depend on MinIO or RabbitMQ, to simplify debugging.

- **Repository alignment & persistence**:
  - Implement/align `AnalyticsRepository` so that:
    - It can save full analytics records into the existing `PostAnalytics` model.
    - It abstracts DB access from the orchestrator and entry points.

- **Metrics & observability hooks (minimal)**:
  - Add lightweight logging and timing around `AnalyticsOrchestrator.process_post`
    so we can later plug in Prometheus metrics without changing core logic.

## Impact

- **Capabilities**:
  - Adds a new **Analytics Orchestration** capability:
    - Single responsibility: transform one Atomic JSON post into a persisted analytics record.
    - Entry-point agnostic: works for both queue-based and API-based flows.
  - Connects existing module capabilities (text preprocessing, intent, keywords, sentiment,
    impact) into a coherent, testable pipeline.

- **Architecture**:
  - Realizes the orchestrator design in `documents/master-proposal.md` Section 3.2/3.3:
    - Orchestrator sits between entry points and the 5-stage pipeline.
    - Persistence handled via repository and `PostAnalytics` schema.
  - Clarifies where to plug in:
    - Retry logic.
    - Metrics and tracing.
    - Future batch processing and caching.

- **Risks / Considerations**:
  - Orchestrator increases coupling between modules if not carefully designed; we will
    keep module invocations simple and rely on existing Input/Output contracts.
  - We must avoid blocking the consumer loop with DB/MinIO/AI bottlenecks; the orchestrator
    will be synchronous but small, relying on existing async/infra layers where appropriate.
  - API entry point is for dev/test only and should be clearly documented as such.


