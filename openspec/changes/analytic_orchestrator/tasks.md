## 1. Capability & Design Alignment

- [x] **Task 1.1**: Align orchestrator design with master proposal and implement_plan  
  - [x] Reconciled `analytic_orchestrator.md`, `documents/implement_plan.md` (Phase 1 & 2),
        and `documents/master-proposal.md` (Sections 3 & 4) to:
        - Confirm the exact 5-stage pipeline (Preprocessor → Intent → Keyword → Sentiment → Impact)
          as the canonical processing order.
        - Clarify Atomic JSON input contract with sections: `meta`, `content`, `interaction`,
          `author`, `comments`, consistent with the MinIO JSON schema.
        - Confirm final DB (`post_analytics`) and API output contracts, reusing the schema and
          response examples already defined in `documents/master-proposal.md`.
  - [x] Captured the orchestrator role, input/output contracts, skip behavior and entry-point
        integration explicitly in `openspec/changes/analytic_orchestrator/design.md`.

- [x] **Task 1.2**: Define orchestration capability spec  
  - [x] Added delta spec under `openspec/changes/analytic_orchestrator/specs/service_lifecycle/spec.md`
        defining:
        - Orchestrator responsibility and boundaries (single-post pipeline runner).
        - Entry points (queue consumer with MinIO, dev/test API with direct JSON).
        - Persistence contract to `post_analytics` via enriched analytics payload.
  - [x] Ensured requirements include:
        - Single-post processing semantics (Atomic JSON in, one analytics record out).
        - Skip logic for SPAM/SEEDING/noise with neutral/LOW defaults when skipped.
        - Deterministic, side-effect free module ordering (Preprocessor → Intent → Keyword
          → Sentiment → Impact) as a core invariant.

## 2. Core Orchestrator Implementation

- [x] **Task 2.1**: Implement `AnalyticsOrchestrator` class  
  - [x] Created `services/analytics/orchestrator.py` with an `AnalyticsOrchestrator` that:
        - Accepts `post_data: dict` (Atomic JSON) and returns a final analytics dict.
        - Holds references to module instances:
          - `TextPreprocessor`
          - `IntentClassifier`
          - `KeywordExtractor`
          - `SentimentAnalyzer` (optional, to allow disabling sentiment layer in some envs).
          - `ImpactCalculator`
        - Uses a repository abstraction for persistence via a simple `save(dict)` call.
  - [x] Implemented `process_post(post_data: dict) -> dict` to:
        - Extract core fields from `meta`, `interaction`, `author`, `comments`.
        - Run Modules 1–5 sequentially, respecting existing I/O contracts from each module.
        - Apply skip logic combining preprocessor stats (e.g. `is_too_short`,
          `has_spam_keyword`) and intent result (`should_skip`) to short-circuit noisy posts.
        - Build final analytics payloads:
          - `_build_skipped_result(...)` for skipped posts with neutral/LOW defaults.
          - `_build_final_result(...)` for fully processed posts, compatible with
            `PostAnalytics` and aligned with `documents/master-proposal.md` output examples.

- [x] **Task 2.2**: Implement skip & fallback strategies  
  - [x] Defined an internal `_build_skipped_result(...)` helper that:
        - Marks posts as skipped but still records essential metadata (intent).
        - Sets neutral defaults for sentiment/impact (NEUTRAL sentiment, LOW risk,
          zero impact score) while preserving raw engagement metrics.
  - [x] Ensured orchestrator can gracefully handle:
        - Missing or partial `interaction` / `author` metrics via `.get(..., 0)` access.
        - Missing `comments` array using safe defaults in `_run_preprocessor`.
        - Partial module failures by:
          - Wrapping keyword extraction in `_run_keywords` and falling back to an
            empty `KeywordResult` when extraction fails.
          - Wrapping sentiment analysis in `_run_sentiment` and falling back to
            a neutral overall result with empty aspects on error or when the
            analyzer is not configured.
          - Wrapping impact calculation in `_run_impact` and falling back to a
            neutral/LOW impact result with zeroed breakdown when calculation fails,
            so a consistent record can still be persisted.

## 3. Infrastructure Adapters & Repository

- [x] **Task 3.1**: MinIO storage adapter  
  - [x] Implemented `infrastructure/storage/minio_client.py` with a `MinioAdapter` that:
        - Wraps the `minio` client using `core.config.Settings` (`minio_endpoint`,
          `minio_access_key`, `minio_secret_key`) for credentials and secure flag.
        - Provides `download_json(bucket: str, object_path: str) -> dict` that:
          - Streams object content from MinIO via `get_object`.
          - Parses JSON directly from the response stream into a Python dict
            without writing temporary files.
        - Logs success/failure via `core.logger` and raises a `RuntimeError` with a clear
          message when fetching or parsing fails, so callers (consumer/orchestrator)
          can handle errors appropriately.

- [x] **Task 3.2**: Analytics repository  
  - [x] Implemented `repositories/analytics_repository.py` with an `AnalyticsRepository` that:
        - Accepts a synchronous SQLAlchemy `Session` in its constructor.
        - Provides `save(analytics_data: dict)` to persist into `models.PostAnalytics`,
          performing an insert-or-update based on the primary key `id` so
          re-processing the same post overwrites the previous analytics record.
        - Provides `get_by_id(post_id: str)` to fetch existing `PostAnalytics` rows.
  - [x] Ensured mapping between orchestrator payload and `PostAnalytics` fields is explicit
        and aligned:
        - `impact_score`, `risk_level`, `is_viral`, `is_kol`.
        - `aspects_breakdown`, `keywords`, `sentiment_probabilities`, `impact_breakdown`.
        - Raw metrics (view/like/comment/share/save/follower counts), timestamps and
          core identifiers (`id`, `project_id`, `platform`, `published_at`, `analyzed_at`).

## 4. Entry Points (Queue & API)

- [x] **Task 4.1**: RabbitMQ consumer integration  
  - [x] Extended `internal/consumers/main.py` to:
        - Parse incoming messages as either:
          - A full Atomic JSON post (`post_data`), or
          - An envelope containing `data_ref` (`bucket`, `path`) pointing to a
            MinIO object.
        - Use `MinioAdapter` (`infrastructure/storage/minio_client.py`) to load
          the Atomic JSON from MinIO when `data_ref` is present.
        - Create a DB session via a local SQLAlchemy session factory using
          `settings.database_url_sync` and `models.database.Base`.
        - Instantiate `AnalyticsRepository` with the DB session and
          `AnalyticsOrchestrator` with that repository (and a `SentimentAnalyzer`
          built from the provided PhoBERT model when available).
        - Delegate all per-post processing to `AnalyticsOrchestrator.process_post(post_data)`
          and log success/failure, relying on `aio_pika` context for ack/nack semantics.
  - [x] Ensured the consumer no longer duplicates pipeline/module logic (keyword,
        sentiment, impact) and instead treats the orchestrator as the single
        entry point for analytics decisions.

- [x] **Task 4.2**: Dev/Test API endpoint  
  - [x] Added a dev/test-only route under `internal/api/routes/orchestrator.py` that:
        - Defines an `OrchestratorRequest` model matching the Atomic JSON structure
          (`meta`, `content`, `interaction`, `author`, `comments`).
        - Exposes `POST /dev/process-post-direct` which:
          - Accepts a full Atomic JSON post body.
          - Creates a synchronous DB session and `AnalyticsRepository`.
          - Optionally builds a `SentimentAnalyzer` from a best-effort `PhoBERTONNX`
            instance for local testing.
          - Delegates to `AnalyticsOrchestrator.process_post(post_data)` and returns
            the final analytics result wrapped in a simple `status` + `data` response.
        - Registers the router in `internal/api/main.py` under the `/dev` prefix to
          clearly indicate it bypasses MinIO and queue and is intended for
          debugging/development only.

## 5. Testing & Validation

- [x] **Task 5.1**: Unit tests for orchestrator  
  - [x] Added `tests/orchestrator/test_unit.py` with comprehensive test coverage:
        - **Happy-path orchestration**: `TestHappyPath` class with tests for full pipeline success
          and complete metrics handling (all modules succeed, result persisted correctly).
        - **Skip logic**: `TestSkipLogic` class covering:
          - Skip for too-short text (`is_too_short` flag).
          - Skip for spam keywords (`has_spam_keyword` flag).
          - Skip for SEEDING intent (`should_skip` from intent classifier).
          - Combination of spam + intent skip conditions (OR logic).
        - **Graceful handling**: `TestGracefulHandling` class covering:
          - Missing interaction metrics (defaults to 0).
          - Missing author metrics (defaults to 0).
          - Missing comments (empty list handled).
          - Missing content text (empty content handled).
          - Missing SentimentAnalyzer (returns neutral defaults).
          - Keyword extraction failures (graceful fallback to empty keywords).
          - Impact calculation failures (graceful fallback to neutral/low impact).
        - **Data mapping**: `TestDataMapping` class covering:
          - Platform normalization to uppercase.
          - Unknown platform defaulting to "UNKNOWN".
          - Aspects breakdown mapping from sentiment result.
  - [x] Used fakes/mocks for all dependencies:
        - `FakeRepository`: Simple in-memory storage for verification.
        - `FakeTextPreprocessor`: Configurable preprocessing results.
        - `FakeIntentClassifier`: Configurable intent classification.
        - `FakeKeywordExtractor`: Configurable keyword extraction.
        - `FakeSentimentAnalyzer`: Configurable sentiment analysis.
        - `FakeImpactCalculator`: Configurable impact calculation.
        - All tests run fast (<5 seconds) without loading real models or databases.

- [x] **Task 5.2**: Integration tests (API & consumer)  
  - [x] Added API integration coverage in `tests/integration/test_api_integration.py`:
        - Extended tests to cover the dev orchestrator endpoint:
          - `test_dev_orchestrator_endpoint_runs_full_pipeline` posts a full Atomic JSON
            to `POST /dev/process-post-direct`, asserts a `SUCCESS` response and verifies
            that a patched `AnalyticsRepository` receives a `PostAnalytics`-shaped payload
            (id, project_id, platform, impact_score, risk_level).
        - Reused existing tests for `/health`, `/` root, `/openapi.json`, and
          `/test/analytics` to ensure the API surface remains consistent.
  - [x] Added consumer integration coverage in `tests/integration/test_consumer_integration.py`:
        - `test_consumer_processes_minio_ref_and_calls_repository`:
          - Patches `MinioAdapter` to return a sample Atomic JSON post for any
            `data_ref` (bucket/path) input.
          - Patches `AnalyticsRepository` to an in-memory fake and `IntentClassifier`
            inside `services.analytics.orchestrator` to return a dict-based result
            compatible with orchestrator skip logic.
          - Constructs a synthetic RabbitMQ `IncomingMessage`-like object and invokes
            the async message handler returned by `create_message_handler`.
          - Asserts that the fake repository is called exactly once with a payload
            containing the expected `id`, normalized `platform`, `impact_score`,
            and `risk_level`, demonstrating an end-to-end orchestrated run without
            requiring a real database, RabbitMQ, or MinIO instance.

## 6. Documentation & OpenSpec Validation

- [x] **Task 6.1**: Documentation updates  
  - [x] Updated `documents/architecture.md` to include a dedicated subsection:
        - **`7.1 Analytics Orchestrator (services/analytics/orchestrator.py)`** describing:
          - The orchestrator's role as the central coordinator for the 5-module pipeline
            (Preprocessor → Intent → Keyword → Sentiment → Impact → Persistence).
          - The two entry points:
            - RabbitMQ consumer (`internal/consumers/main.py`) using `MinioAdapter` to load
              Atomic JSON from MinIO and delegating to `AnalyticsOrchestrator.process_post`.
            - Dev/Test API endpoint (`internal/api/routes/orchestrator.py`, `POST /dev/process-post-direct`)
              that accepts Atomic JSON directly and calls the orchestrator for debugging.
          - A text diagram showing the end-to-end flow:
            - MinIO → Consumer → Orchestrator → Repository → PostgreSQL.
            - Dev/Test API → Orchestrator → Repository → PostgreSQL.

- [x] **Task 6.2**: OpenSpec validation  
  - [x] Ran `openspec validate analytic_orchestrator --strict` and confirmed the change is valid.
  - [x] Verified that existing spec deltas under
        `openspec/changes/analytic_orchestrator/specs/service_lifecycle/spec.md` already
        describe orchestrator behavior and entry points accurately, so no additional
        spec edits were required for this task.


