# impact_risk Specification

## Purpose
TBD - created by archiving change implement_impact_risk_calculator. Update Purpose after archive.
## Requirements
### Requirement: Impact Score Computation

The Analytics Engine SHALL compute a normalized **Impact Score** in the range
0–100 for each processed post, based on engagement, reach, platform and
sentiment, as defined in the Quantitative Analysis Engine (Module 5) model.

#### Scenario: High engagement KOL post

- **Given** a post with:
  - 100,000 views, 5,000 likes, 800 comments, 300 shares, 150 saves  
  - Author followers = 100,000 and `is_verified = true`  
  - Platform = "TIKTOK" (platform multiplier 1.0)  
  - Overall sentiment label "NEGATIVE" with strong negative score
- **When** the Impact & Risk Calculator runs
- **Then** the system SHALL:
  - Compute an Engagement Score using the configured weights where
    shares > saves > comments > likes > views.
  - Compute a Reach Score using log₁₀(followers+1), with a verified bonus > 1.0.
  - Apply platform and sentiment multipliers (higher for NEGATIVE).
  - Normalize the resulting raw impact to a 0–100 Impact Score, saturating at 100
    when RawImpact exceeds the configured MAX_RAW_SCORE_CEILING.

#### Scenario: Low engagement negative post from small account

- **Given** a post with:
  - 50 views, 5 likes, 1 comment, 0 shares, 0 saves  
  - Author followers = 10 and `is_verified = false`  
  - Overall sentiment label "NEGATIVE"
- **When** the Impact & Risk Calculator runs
- **Then** the system SHALL:
  - Produce a low Impact Score (e.g. < 10) reflecting minor business relevance.

### Requirement: Risk Level Classification

The Analytics Engine SHALL classify each post into a discrete **Risk Level**
(`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) based on Impact Score, sentiment and
author influence (KOL), using a configurable risk matrix.

#### Scenario: Critical KOL crisis

- **Given** a post with:
  - Impact Score ≥ 70 (high impact)  
  - Overall sentiment label "NEGATIVE" (strongly negative)  
  - `is_kol = true` (followers ≥ configured KOL threshold)
- **When** the Impact & Risk Calculator evaluates risk
- **Then** the system SHALL:
  - Assign `risk_level = "CRITICAL"`.
  - Set `is_viral = true`.

#### Scenario: High risk non-KOL crisis

- **Given** a post with:
  - Impact Score ≥ 70 (high impact)  
  - Overall sentiment label "NEGATIVE"  
  - `is_kol = false`
- **When** the Impact & Risk Calculator evaluates risk
- **Then** the system SHALL:
  - Assign `risk_level = "HIGH"`.

#### Scenario: Medium and low risk

- **Given** posts with:
  - Medium Impact Score (≥ 40 but < 70) and negative sentiment, OR
  - High Impact Score (≥ 60) but neutral/positive sentiment
- **When** the Impact & Risk Calculator evaluates risk
- **Then** the system SHALL:
  - Assign `risk_level = "MEDIUM"` for the above cases.
- **And Given** all other combinations (low impact and/or non-negative sentiment)
- **When** the calculator evaluates risk
- **Then** the system SHALL:
  - Assign `risk_level = "LOW"`.

### Requirement: Viral & KOL Detection Flags

The Analytics Engine SHALL expose explicit boolean flags for **viral posts**
and **KOL-driven posts** to support dashboards and alerting.

#### Scenario: Viral post detection

- **Given** a post with Impact Score ≥ the configured Viral threshold
  (e.g. ≥ 70)
- **When** the Impact & Risk Calculator runs
- **Then** the system SHALL:
  - Set `is_viral = true` in the impact output.

#### Scenario: KOL detection

- **Given** a post whose author has followers ≥ the configured KOL threshold
  (e.g. ≥ 50,000)
- **When** the Impact & Risk Calculator runs
- **Then** the system SHALL:
  - Set `is_kol = true` in the impact output.

### Requirement: Impact & Risk Output Contract

The Analytics Engine SHALL include Impact & Risk fields in the final analytics
result and database record for each processed post, in alignment with
`master-proposal.md`.

#### Scenario: Persist and expose impact metrics

- **Given** a successfully processed post
- **When** the pipeline completes Modules 1–5
- **Then** the final analytics result and persisted record SHALL contain:
  - `impact_score` (0–100 float)
  - `risk_level` ("LOW" | "MEDIUM" | "HIGH" | "CRITICAL")
  - `is_viral` (bool)
  - `is_kol` (bool)
  - `impact_breakdown` (structured JSON) with:
    - `engagement_score`
    - `reach_score`
    - `platform_multiplier`
    - `sentiment_amplifier`
    - `raw_impact`

### Requirement: Performance & Determinism

The Impact & Risk Calculator SHALL be deterministic and efficient, adding
negligible latency compared to AI inference steps.

#### Scenario: Fast and deterministic computation

- **Given** a single post’s metrics (`interaction`, `author`, `sentiment`, `platform`)
- **When** Impact & Risk calculation runs repeatedly with identical inputs
- **Then** the system SHALL:
  - Produce identical ImpactScore, RiskLevel, `is_viral`, `is_kol` and breakdown
    values (no randomness).
  - Complete computation within **< 5ms** per post on typical production hardware,
    ensuring Module 5 is not a throughput bottleneck.

