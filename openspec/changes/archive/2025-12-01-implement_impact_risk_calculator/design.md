## Design: Impact & Risk Calculator (Module 5)

**Change ID**: `implement_impact_risk_calculator`  
**Related Docs**:
- `documents/module_phase_5.md`
- `documents/implement_plan.md`
- `documents/master-proposal.md`

### 1. Context

The analytics engine already implements:
- Module 1: `TextPreprocessor` – clean & merge content.
- Module 2: `IntentClassifier` – fast spam/seeding filtering.
- Module 3: `KeywordExtractor` – aspect-aware keyword extraction.
- Module 4: `SentimentAnalyzer` – overall & aspect-based sentiment (ABSA).

Module 5 (“Impact & Risk Calculator”) is the final step in the pipeline:
it turns raw engagement, reach and sentiment into:
- A normalized **Impact Score** (0–100).
- A discrete **Risk Level** (LOW/MEDIUM/HIGH/CRITICAL).
- Flags for **is_viral** and **is_kol**.

This design consolidates the math model described in `module_phase_5.md` and
ensures it aligns with:
- The database output contract (`post_analytics`).
- The orchestrator/API structure in `master-proposal.md`.

### 2. Goals / Non-Goals

**Goals**
- Implement a deterministic, configurable ImpactCalculator module that:
  - Consumes only primitive metrics (integers, floats, labels).
  - Does not perform any I/O (no DB, no network).
  - Can be safely reused by the orchestrator and offline batch jobs.
- Provide a clear risk matrix tuned for:
  - Viral negative posts.
  - KOL-driven crises.
  - Positive viral campaigns.
- Keep computation extremely fast (<5ms) to avoid adding latency.

**Non-Goals**
- No additional AI/ML models: this is pure business logic, not ML training.
- No changes to crawler/MinIO formats (consume existing JSON only).
- No changes to downstream dashboard queries (they will consume the new fields).

### 3. Data Flow & Interfaces

#### 3.1 Inputs to ImpactCalculator

From orchestrator / pipeline:

- `interaction` (dict-like):
  - `views`: int
  - `likes`: int
  - `comments_count`: int
  - `shares`: int
  - `saves`: int
  - (optionally) `platform`: str (if not passed separately)

- `author`:
  - `followers`: int
  - `is_verified`: bool

- `sentiment_overall` (output of SentimentAnalyzer overall):
  - `label`: "NEGATIVE" | "NEUTRAL" | "POSITIVE"
  - `score`: float in [-1.0, 1.0] (SCORE_MAP-based)

- `platform`: string:
  - "TIKTOK" | "FACEBOOK" | "YOUTUBE" | "INSTAGRAM" | "UNKNOWN"

#### 3.2 Outputs from ImpactCalculator

Returned dict:

- `impact_score`: float ∈ [0, 100] (rounded to 2 decimals).
- `risk_level`: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL".
- `is_viral`: bool.
- `is_kol`: bool.
- `breakdown`:
  - `engagement_score`: float
  - `reach_score`: float
  - `platform_multiplier`: float
  - `sentiment_amplifier`: float
  - `raw_impact`: float

These fields map directly into:
- DB: `impact_score`, `risk_level`, `is_viral`, `is_kol`, `impact_breakdown`.
- API: `impact_metrics` / `impact_breakdown` sections in response.

### 4. Math Model

#### 4.1 Engagement Score

Weighted sum of interactions (per `module_phase_5.md`):

- Views have minimal weight.
- Shares > Saves > Comments > Likes > Views.

Example (exact constants configurable):

```python
E_raw = (
    views    * WEIGHT_VIEW
  + likes    * WEIGHT_LIKE
  + comments * WEIGHT_COMMENT
  + saves    * WEIGHT_SAVE
  + shares   * WEIGHT_SHARE
)
```

Default weights (from module_phase_5.md):
- `WEIGHT_VIEW   = 0.01`
- `WEIGHT_LIKE   = 1.0`
- `WEIGHT_COMMENT = 2.0`
- `WEIGHT_SAVE   = 3.0`
- `WEIGHT_SHARE  = 5.0`

#### 4.2 Reach Score

Logarithmic scale of followers:

```python
R_score = log10(followers + 1)
if author.is_verified:
    R_score *= 1.2
```

This compresses the long tail of followers so that:
- 100 followers → ~2.0
- 10,000 followers → ~4.0
- 1,000,000 followers → ~6.0

#### 4.3 Platform & Sentiment Multipliers

- Platform multipliers (from module_phase_5.md and master-proposal):
  - TIKTOK: 1.0
  - FACEBOOK: 1.2
  - YOUTUBE: 1.5
  - INSTAGRAM: 1.1
  - UNKNOWN: 1.0

- Sentiment amplifiers:
  - NEGATIVE: 1.5 (negative crises are more dangerous).
  - NEUTRAL: 1.0.
  - POSITIVE: 1.1 (brand love/viral positivity still important but less risk).

#### 4.4 Raw Impact and Normalization

```python
RawImpact = E_raw * R_score * M_platform * M_sentiment
ImpactScore = min(100.0, (RawImpact / MAX_RAW_SCORE_CEILING) * 100)
```

`MAX_RAW_SCORE_CEILING` is a tuning constant (e.g. 100_000) chosen so that
typical high-impact posts land near 100 on the 0–100 scale.

### 5. Risk Matrix

Based on `module_phase_5.md`:

- **CRITICAL**:
  - High ImpactScore (≥ 70) AND
  - Negative sentiment AND
  - KOL (followers ≥ KOL_FOLLOWERS_THRESHOLD, e.g. 50k).

- **HIGH**:
  - High ImpactScore (≥ 70) AND
  - Negative sentiment (non-KOL).

- **MEDIUM**:
  - Medium impact (≥ 40) AND negative sentiment.
  - OR High impact (≥ 60) but neutral/positive (viral but not negative).

- **LOW**:
  - All other cases (low impact, non-negative, small accounts).

The final `_assess_risk` function will implement this logic using:
- `impact_score` (0–100).
- `sentiment_label` ("NEGATIVE", "NEUTRAL", "POSITIVE").
- `is_kol` boolean.

### 6. Configuration Strategy

- Introduce an `ImpactConfig` or reuse `core/config.py` with:
  - Interaction weights.
  - Platform multipliers.
  - Sentiment amplifiers.
  - Thresholds: VIRAL, KOL followers, MAX_RAW_SCORE_CEILING.
- Where appropriate, allow overrides via environment variables, but keep safe
  defaults in code to match the math in `module_phase_5.md`.

### 7. Integration Points

#### 7.1 Orchestrator

In the orchestrator (as sketched in `implement_plan.md`):

1. Run Modules 1–4 to obtain:
   - `clean_text`, `intent_result`, `keywords`, `sentiment`.
2. Build metrics:
   - `interaction` from `post_data["interaction"]`.
   - `author` from `post_data["author"]`.
   - `platform` from `post_data["meta"]["platform"]`.
3. Call:

```python
impact = impact_calculator.calculate(
    interaction=interaction,
    author=author,
    sentiment=sentiment["overall"],
    platform=platform,
)
```

4. Merge `impact` into the final result passed to persistence/API.

#### 7.2 Persistence & API

- DB model `post_analytics` already includes fields for:
  - `impact_score`, `risk_level`, `is_viral`, `is_kol`, `impact_breakdown`.
- API responses (per master-proposal) should surface these under
  `impact_metrics` or equivalent block so that dashboards and alerts
  can consume them directly.

### 8. Risks / Trade-offs

- **Calibration risk**:
  - Poorly chosen weights or thresholds could mis-label posts as LOW vs HIGH.
  - Mitigation: keep all weights in config, and validate with real business data.

- **Coupling to sentiment**:
  - Risk level depends on sentiment correctness; if sentiment drifts, risk
    classification may misfire.
  - Mitigation: sentiment quality is enforced separately via the
    `update_sentiment_model` change and its semantic tests.

- **Performance**:
  - Math is simple (adds, multiplies, logs), so CPU overhead is negligible.
  - No external I/O in ImpactCalculator keeps latency <5ms.

### 9. Open Questions

- Should there be separate thresholds for different platforms (e.g. higher
  VIRAL_THRESHOLD for TikTok vs Facebook)?
- Should RiskLevel also consider **aspect-level** sentiment (e.g. crisis only
  when PERFORMANCE or SAFETY aspects are negative)?
- Do business users want a separate “Opportunity” score for highly positive
  viral posts, or is ImpactScore + LOW risk sufficient?


