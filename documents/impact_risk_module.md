## Module 5: Impact & Risk Calculator

Module 5 converts raw engagement, reach and sentiment into a normalized
**Impact Score (0–100)** and a discrete **Risk Level** for each post.

### 1. Inputs

- **Interaction metrics** (`interaction`):
  - `views`: int
  - `likes`: int
  - `comments_count`: int
  - `shares`: int
  - `saves`: int
- **Author metrics** (`author`):
  - `followers`: int
  - `is_verified`: bool
- **Overall sentiment** (`sentiment_overall`):
  - `label`: `"NEGATIVE" | "NEUTRAL" | "POSITIVE"`
  - `score`: float in \[-1.0, 1.0] (ABSA overall score)
- **Platform**:
  - `"TIKTOK" | "FACEBOOK" | "YOUTUBE" | "INSTAGRAM" | "UNKNOWN"`

### 2. Formula

#### 2.1 Engagement Score

Weighted sum of interactions:

```python
E = (
    views          * IMPACT_WEIGHT_VIEW
    + likes        * IMPACT_WEIGHT_LIKE
    + comments_cnt * IMPACT_WEIGHT_COMMENT
    + saves        * IMPACT_WEIGHT_SAVE
    + shares       * IMPACT_WEIGHT_SHARE
)
```

Default weights (configurable via `core/config.Settings`):

- `IMPACT_WEIGHT_VIEW = 0.01`
- `IMPACT_WEIGHT_LIKE = 1.0`
- `IMPACT_WEIGHT_COMMENT = 2.0`
- `IMPACT_WEIGHT_SAVE = 3.0`
- `IMPACT_WEIGHT_SHARE = 5.0`

#### 2.2 Reach Score

Log-scale followers with verified bonus:

```python
R = log10(followers + 1)
if is_verified:
    R *= 1.2
```

#### 2.3 Platform & Sentiment Multipliers

- Platform multipliers:
  - TIKTOK: 1.0
  - FACEBOOK: 1.2
  - YOUTUBE: 1.5
  - INSTAGRAM: 1.1
  - UNKNOWN: 1.0
- Sentiment amplifiers:
  - NEGATIVE: 1.5
  - NEUTRAL: 1.0
  - POSITIVE: 1.1

#### 2.4 Raw Impact & Normalization

```python
RawImpact = E * R * M_platform * M_sentiment
ImpactScore = min(100.0, max(0.0, (RawImpact / MAX_RAW_SCORE_CEILING) * 100.0))
```

Where `MAX_RAW_SCORE_CEILING` (default `100_000.0`) is tuned so that
“crisis” posts land near 100 and silent users remain near 0.

### 3. Risk Levels

Risk is derived from three signals:

- `impact_score` (0–100)
- `sentiment_overall.label` (`NEGATIVE`, `NEUTRAL`, `POSITIVE`)
- `is_kol` (followers ≥ `IMPACT_KOL_FOLLOWER_THRESHOLD`, default 50,000)

Matrix:

- **CRITICAL**:
  - `impact_score ≥ 70`, label = NEGATIVE, `is_kol = True`.
- **HIGH**:
  - `impact_score ≥ 70`, label = NEGATIVE, `is_kol = False`.
- **MEDIUM**:
  - `40 ≤ impact_score < 70` and label = NEGATIVE, **or**
  - `impact_score ≥ 60` and label in {NEUTRAL, POSITIVE}.
- **LOW**:
  - All remaining combinations.

### 4. Output Contract

`ImpactCalculator.calculate(...)` returns:

```python
{
    "impact_score": float,            # 0–100
    "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
    "is_viral": bool,                 # impact_score ≥ IMPACT_VIRAL_THRESHOLD
    "is_kol": bool,                   # followers ≥ IMPACT_KOL_FOLLOWER_THRESHOLD
    "impact_breakdown": {
        "engagement_score": float,
        "reach_score": float,
        "platform_multiplier": float,
        "sentiment_amplifier": float,
        "raw_impact": float,
    },
}
```

### 5. Examples

#### Crisis (KOL, high engagement, negative)

- Followers: 100,000 (verified)
- Metrics: very high views/likes/comments/shares
- Sentiment: NEGATIVE

Expected:

- `impact_score` ≳ 80
- `risk_level = "CRITICAL"`
- `is_viral = True`, `is_kol = True`

#### Silent user (low engagement, negative)

- Followers: 10
- Metrics: very low
- Sentiment: NEGATIVE

Expected:

- `impact_score < 10`
- `risk_level = "LOW"`
- `is_viral = False`, `is_kol = False`

#### Brand love (viral positive)

- Followers: 80,000 (verified)
- Metrics: viral
- Sentiment: POSITIVE

Expected:

- `impact_score ≳ 80`
- `risk_level` in {LOW, MEDIUM} (viral but not crisis)
- `is_viral = True`, `is_kol = True`


