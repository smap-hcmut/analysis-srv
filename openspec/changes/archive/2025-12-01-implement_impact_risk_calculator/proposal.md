## Change: Implement Impact & Risk Calculator (Module 5)

**Change ID**: `implement_impact_risk_calculator`  
**Status**: Draft  
**Related Docs**:
- `documents/module_phase_5.md`
- `documents/implement_plan.md`
- `documents/master-proposal.md`

## Why

The current analytics pipeline (Modules 1–4) can:
- Clean and normalize text (TextPreprocessor).
- Filter noise and categorize intent (IntentClassifier).
- Extract aspect-aware keywords (KeywordExtractor).
- Compute overall and aspect-based sentiment (SentimentAnalyzer).

However, it still lacks a **quantitative impact layer** that turns raw metrics
(views, likes, shares, followers, sentiment) into actionable **Impact Scores**
and **Risk Levels** that business users can interpret at a glance. The
`master-proposal.md` and `module_phase_5.md` both define a dedicated
**Impact & Risk Calculator (Module 5)** as the “Kế toán” of the system:
- Convert raw engagement into a normalized 0–100 impact score.
- Flag viral posts and KOL posts explicitly.
- Classify risk levels (LOW/MEDIUM/HIGH/CRITICAL) to drive alerts and dashboards.

Without this module:
- Downstream dashboards and alerting cannot prioritize which posts matter most.
- Crisis detection relies only on sentiment, ignoring reach and engagement.
- There is no consistent, reproducible mapping from raw metrics to business KPIs.

## What Changes

- **New Impact & Risk Calculator module (Module 5)**:
  - Implement a pure-Python `ImpactCalculator` service in
    `services/analytics/impact/impact_calculator.py` that:
    - Computes **Engagement Score** as a weighted sum of likes, comments, saves and shares.
    - Computes **Reach Score** using log₁₀(followers+1), with a multiplier for verified accounts.
    - Applies **Platform multipliers** (TikTok/Facebook/YouTube/…).
    - Applies **Sentiment amplifiers** to emphasize negative crises.
    - Produces a normalized 0–100 **impact_score** plus `is_viral` and `is_kol` flags.
    - Classifies **risk_level** using a risk matrix that combines impact, sentiment and KOL status.

- **Configuration extraction**:
  - Introduce a dedicated configuration surface (either a small config class or additions to
    `core/constants.py` / `core/config.py`) for:
    - Interaction weights (view/like/comment/save/share).
    - Platform weights.
    - Sentiment amplifiers.
    - Thresholds (viral score, KOL followers, max raw score ceiling).

- **Pipeline integration**:
  - Wire the new `ImpactCalculator` into the orchestration layer so that:
    - After Modules 1–4 run, Module 5 is called with:
      - Engagement metrics (views/likes/comments/shares/saves).
      - Author metrics (followers, verified flag).
      - Overall sentiment output from `SentimentAnalyzer`.
    - The final analytics result includes:
      - `impact_score`, `risk_level`, `is_viral`, `is_kol`.
      - A detailed `impact_breakdown` JSON structure for debugging.

- **Persistence & API alignment**:
  - Ensure the database schema (e.g. `post_analytics` table) and public API
    response fields align with the Impact & Risk output contract described in
    `master-proposal.md` and `module_phase_5.md`.

- **Testing & documentation**:
  - Add unit tests for `ImpactCalculator` to cover:
    - High-impact crisis scenarios (CRITICAL).
    - Low-engagement negatives (LOW/MEDIUM).
    - Positive viral posts (LOW risk but high impact).
  - Update high-level docs (`README.md` or a dedicated module doc) to explain:
    - The formulas (Engagement, Reach, Impact, Risk).
    - The meaning of each risk level and when alerts should fire.

## Impact

- **Specs**:
  - Adds a new capability spec for **impact and risk calculation** under
    `openspec/specs/impact_risk/spec.md`, defining:
    - ImpactScore requirement (0–100).
    - RiskLevel classification requirement.
    - Viral/KOL detection requirement.
    - Performance and determinism requirements.

- **Code**:
  - New module:
    - `services/analytics/impact/impact_calculator.py`
  - New tests:
    - `tests/impact/test_unit.py` (and optionally `test_integration.py` / `test_performance.py`)
  - Configuration:
    - Small additions to `core/config.py` / `core/constants.py` to centralize weights and thresholds.
  - Orchestrator:
    - Minimal changes to the existing pipeline/orchestrator code to call ImpactCalculator
      and include its output in the final analytics result.

- **Business**:
  - Enables dashboards and alerting systems to:
    - Sort and filter posts by **Impact Score** and **Risk Level** instead of raw counts.
    - Quickly identify:
      - Viral negative posts from KOLs (CRITICAL).
      - Medium-risk complaints with growing engagement.
      - Positive viral campaigns (high impact but low risk).
  - Aligns implementation with the business-level expectations in `master-proposal.md`
    for Module 5: the “Quantitative Analysis Engine”.


