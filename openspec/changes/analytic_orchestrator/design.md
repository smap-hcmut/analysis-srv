## Design: Analytics Orchestrator & Entry Points

**Change ID**: `analytic_orchestrator`  
**Related Docs**:
- `analytic_orchestrator.md`
- `documents/master-proposal.md`
- `documents/implement_plan.md`

### 1. Context

The Analytics Engine already has:
- Module 1: `TextPreprocessor` (clean & merge content).
- Module 2: `IntentClassifier` (noise/intent filter).
- Module 3: `KeywordExtractor` (aspect-aware keywords).
- Module 4: `SentimentAnalyzer` (overall + ABSA).
- Module 5: `ImpactCalculator` (impact score & risk).

`documents/master-proposal.md` and `analytic_orchestrator.md` describe an
**Analytics Orchestrator** that:
- Receives **Atomic JSON** posts (from MinIO or directly via API).
- Executes the 5-stage pipeline sequentially.
- Applies skip logic (spam/seeding/noise).
- Persists results into `post_analytics`.

This design document clarifies how the orchestrator fits into the current
codebase and how entry points (RabbitMQ consumer, dev API) will delegate to it.

### 2. Goals / Non-Goals

**Goals**
- Provide a single orchestration component that:
  - Processes one Atomic JSON post at a time.
  - Uses existing modules via their public APIs.
  - Produces a payload compatible with `PostAnalytics` and API responses.
- Add entry points that:
  - Use MinIO + RabbitMQ for production processing.
  - Expose a dev/test-friendly API route that bypasses MinIO/queue.
- Keep orchestration logic small, testable, and free of business logic
  that belongs inside Modules 1–5.

**Non-Goals**
- No new AI capabilities (all ML logic remains in existing modules).
- No major changes to `PostAnalytics` schema (reuse current columns).
- No full batch-processing or retry framework (reserved for later phases).

### 3. Orchestrator Responsibilities

**Class**: `AnalyticsOrchestrator` (in `services/analytics/orchestrator.py`)

Responsibilities:
- Accept a single `post_data: dict` representing an Atomic JSON file.
- Extract required sections:
  - `meta`: id, platform, project_id, published_at, etc.
  - `content`: text, transcription, hashtags, etc.
  - `interaction`: views, likes, comments_count, shares, saves.
  - `author`: followers, is_verified, username, etc.
  - `comments`: comment list for keyword/merge context.
- Run modules sequentially:
  1. **Preprocessor**: get `clean_text`, stats, source breakdown.
  2. **Intent**: classify primary intent and `should_skip`.
  3. **Keyword**: extract aspect-labelled keywords.
  4. **Sentiment**: compute overall + aspect-level sentiment.
  5. **Impact**: compute `impact_score`, `risk_level`, `is_viral`, `is_kol`.
- Apply skip logic combining:
  - Preprocessor signals (e.g., `is_too_short`, spam heuristics).
  - Intent `should_skip` for SEEDING/SPAM.
- Build a final analytics dict containing:
  - All fields required by `models.PostAnalytics`.
  - Rich JSON breakdowns: `aspects_breakdown`, `keywords`,
    `sentiment_probabilities`, `impact_breakdown`.
- Delegate persistence to a repository (`AnalyticsRepository`).

### 4. Entry Points & Data Flow

#### 4.1 RabbitMQ Consumer (Production)

- Existing consumer (`internal/consumers/main.py`) currently:
  - Reads a message body.
  - Logs basic info.
  - Optionally uses SpacyYake & PhoBERT directly.
- With this change:
  - A dedicated consumer function or extended handler will:
    - Parse incoming message containing a `data_ref` (`bucket`, `path`) or atomic
      post JSON directly.
    - Use `MinioAdapter` when a `data_ref` is present to fetch the post JSON.
    - Call `AnalyticsOrchestrator.process_post(post_data)` to run all 5 modules.
    - Let the orchestrator/repository persist to DB.
    - Ack/Nack the RabbitMQ message based on success/failure.

#### 4.2 Dev/Test API Endpoint

- A FastAPI route under `internal/api/routes/` (e.g. `/dev/process-post-direct`) will:
  - Accept a full Atomic JSON payload in the request body.
  - Inject or construct `AnalyticsOrchestrator`.
  - Call `process_post(post_data)` synchronously.
  - Return:
    - `status`: SUCCESS/FAILED.
    - `data`: final analytics dict (including impact, aspects, etc.).
  - This endpoint skips MinIO/queue; it is intended for:
    - Manual debugging.
    - Golden dataset evaluation.
    - Rapid iteration on pipeline tuning.

### 5. Interfaces & Contracts

#### 5.1 Input: Atomic Post JSON

Based on `documents/master-proposal.md` and `documents/implement_plan.md`, the
orchestrator expects a dict with at least:

- `meta`: `{ id, platform, project_id, published_at, ... }`
- `content`: `{ text, transcription, hashtags, ... }`
- `interaction`: `{ views, likes, comments_count, shares, saves }`
- `author`: `{ followers, is_verified, ... }`
- `comments`: `[...]` (optional, defaults to `[]`)

The exact schema is aligned with the MinIO JSON specification used by the crawler.

#### 5.2 Output: Analytics Payload

The orchestrator returns a dict that can be passed to `PostAnalytics` and API:

- `id`, `project_id`, `platform`, `published_at`.
- `overall_sentiment`, `overall_sentiment_score`, `overall_confidence`.
- `primary_intent`, `intent_confidence`.
- `impact_score`, `risk_level`, `is_viral`, `is_kol`.
- JSONB content:
  - `aspects_breakdown` (from SentimentAnalyzer).
  - `keywords` (from KeywordExtractor).
  - `sentiment_probabilities` (overall probabilities).
  - `impact_breakdown` (from ImpactCalculator).
- Raw metrics:
  - `view_count`, `like_count`, `comment_count`, `share_count`,
    `save_count`, `follower_count`.
- Processing metadata:
  - `processing_time_ms`, `model_version` (when available).

#### 5.3 Skip Result Contract

When a post is **skipped** (spam/seeding/noise), the orchestrator will:
- Still persist a record with:
  - Neutral sentiment defaults.
  - LOW impact and LOW risk.
  - Intent set to SEEDING/SPAM (as detected).
  - `is_relevant = False` / `relevance_reason` when these fields are added.
- This keeps downstream dashboards consistent: every crawled post has a record,
  but only relevant ones have meaningful analytics.

### 6. Dependencies & Composition

- `AnalyticsOrchestrator` depends on:
  - `services.analytics.preprocessing.TextPreprocessor`.
  - `services.analytics.intent.IntentClassifier`.
  - `services.analytics.keyword.KeywordExtractor`.
  - `services.analytics.sentiment.SentimentAnalyzer`.
  - `services.analytics.impact.ImpactCalculator`.
  - `repositories.analytics_repository.AnalyticsRepository`.

Construction options:
- For API/dev:
  - Use dependency-injection helpers (e.g. in `core/dependencies.py`) to
    create orchestrator with a DB session and shared model instances.
- For consumer:
  - Reuse existing AI instances (PhoBERT, SpacyYake) when available, and
    inject them into the modules the orchestrator uses where appropriate.

### 7. Risks & Trade-offs

- **Risk**: Orchestrator becomes a “god class”.
  - Mitigation: Keep orchestration limited to call ordering and skip decisions;
    do not duplicate module internals or business rules.
- **Risk**: Tight coupling to transport (RabbitMQ, FastAPI).
  - Mitigation: Entry points only pass `post_data` dicts; orchestrator knows
    nothing about queues or HTTP.
- **Risk**: DB or MinIO failures impacting pipeline.
  - Mitigation: Clearly surface exceptions at entry point level; later phases
    can add retries, DLQ, and circuit breakers around the orchestrator.

### 8. Open Questions

- Should orchestration be fully synchronous only, or expose async APIs as well?
- How much of the skip logic should be configurable (e.g. thresholds from config)?
- When batch-processing is implemented, should multiple posts share a single
  orchestrator instance, or is per-post instantiation acceptable?


