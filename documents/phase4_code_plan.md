# Phase 4: Code Plan — Business Logic Upgrade

**⚠️ IMPORTANT NOTE - ACTUAL IMPLEMENTATION:**

- **Actual Schema**: `schema_analysis` (NOT `analytics` as in this plan)
- **Actual Table**: `post_insight` (NOT `post_analytics` as in this plan)
- **Actual Helper**: `transform_to_post_insight()` (NOT `transform_to_post_analytics()`)
- **Reference**: See `internal/model/post_insight.py` and `internal/post_insight/repository/postgre/helpers.py`

---

**Ref:** `documents/master-proposal.md` (Phase 4), `refactor_plan/05_business_logic.md`
**Convention:** `documents/convention/`
**Depends on:** Phase 1 + Phase 2 + Phase 3 (done)

---

## 0. SCOPE

Implement các business logic mới để populate Phase 4 fields trong `analytics.post_analytics`:

**Fields hiện đang hardcode defaults (Phase 3):**

- `engagement_score` → 0.0
- `virality_score` → 0.0
- `influence_score` → 0.0
- `content_quality_score` → 0.0
- `is_bot` → False
- `language` → None
- `language_confidence` → 0.0
- `toxicity_score` → 0.0
- `is_toxic` → False
- `sentiment_explanation` → None
- `risk_factors` → []

**Phase 4 sẽ implement:**

1. Engagement Score calculation
2. Virality Score calculation
3. Influence Score calculation
4. Multi-factor Risk Assessment (nâng cấp từ simple 4-level)
5. Spam Detection heuristics (nâng cấp từ intent-based)

**OUT OF SCOPE (Phase sau):**

- Language detection (cần thêm library)
- Toxicity detection (cần model mới)
- Bot detection (cần behavioral analysis)
- Content quality score (cần NLP features)
- Sentiment explanation (cần explainable AI)

---

## 1. FILE PLAN

### 1.1 Files sửa (MODIFY)

| #   | File                                                        | Thay đổi                                                                                                  |
| --- | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 1   | `internal/impact_calculation/usecase/impact_calculation.py` | Thêm methods: `calculate_engagement_score()`, `calculate_virality_score()`, `calculate_influence_score()` |
| 2   | `internal/impact_calculation/usecase/impact_calculation.py` | Nâng cấp `_calculate_risk()` → multi-factor risk với crisis keywords + virality amplifier                 |
| 3   | `internal/impact_calculation/type.py`                       | Thêm output fields: `engagement_score`, `virality_score`, `influence_score`, `risk_factors`               |
| 4   | `internal/impact_calculation/constant.py`                   | Thêm constants: `CRISIS_KEYWORDS`, engagement weights, virality thresholds                                |
| 5   | `internal/text_preprocessing/usecase/preprocessing.py`      | Thêm method: `detect_spam()` với heuristics                                                               |
| 6   | `internal/text_preprocessing/type.py`                       | Thêm output field: `is_spam`, `spam_reasons`                                                              |
| 7   | `internal/text_preprocessing/constant.py`                   | Thêm constants: `ADS_KEYWORDS`, `MIN_TEXT_LENGTH`, `MIN_WORD_DIVERSITY`                                   |
| 8   | `internal/analytics/usecase/usecase.py`                     | Integrate Phase 4 calculations vào pipeline                                                               |
| 9   | `internal/analytics/type.py`                                | Update `AnalyticsResult` với Phase 4 fields                                                               |
| 10  | `internal/analyzed_post/repository/postgre/helpers.py`      | Update `transform_to_post_analytics()` để map Phase 4 fields                                              |

### 1.2 Files KHÔNG đổi

- Phase 1/2/3 implementation — giữ nguyên
- Sentiment analysis module — giữ nguyên
- Keyword extraction module — giữ nguyên
- Intent classification module — giữ nguyên

---

## 2. CHI TIẾT TỪNG FILE

### 2.1 `internal/impact_calculation/constant.py` — Thêm Constants

Thêm vào cuối file:

```python
# === PHASE 4: NEW CONSTANTS ===

# Engagement Score Weights
ENGAGEMENT_WEIGHT_LIKE = 1
ENGAGEMENT_WEIGHT_COMMENT = 2
ENGAGEMENT_WEIGHT_SHARE = 3
ENGAGEMENT_MIN_VIEWS_FOR_NORMALIZATION = 100
ENGAGEMENT_SCORE_CAP = 100.0

# Virality Score
VIRALITY_DENOMINATOR_OFFSET = 1  # Avoid division by zero

# Influence Score
INFLUENCE_FOLLOWER_DIVISOR = 1_000_000  # Normalize to millions

# Crisis Keywords (Vietnamese + English)
CRISIS_KEYWORDS = [
    "scam", "lừa đảo", "lừa", "gian lận",
    "cháy", "nổ", "tai nạn", "chết",
    "tẩy chay", "phốt", "scandal",
    "nguy hiểm", "độc hại", "kém chất lượng",
]

# Risk Assessment Thresholds
RISK_SENTIMENT_NEGATIVE_THRESHOLD = -0.3
RISK_SENTIMENT_EXTREME_THRESHOLD = -0.7
RISK_KEYWORD_WEIGHT = 0.4
RISK_SENTIMENT_BASE_WEIGHT = 0.3
RISK_SENTIMENT_EXTREME_WEIGHT = 0.2
RISK_VIRALITY_AMPLIFIER_THRESHOLD = 0.1
RISK_VIRALITY_AMPLIFIER_MIN_BASE = 0.3

# Risk Score Thresholds
RISK_SCORE_CRITICAL_THRESHOLD = 0.8
RISK_SCORE_HIGH_THRESHOLD = 0.6
RISK_SCORE_MEDIUM_THRESHOLD = 0.3

# Risk Factor Labels
RISK_FACTOR_NEGATIVE_SENTIMENT = "NEGATIVE_SENTIMENT"
RISK_FACTOR_EXTREME_NEGATIVE = "EXTREME_NEGATIVE"
RISK_FACTOR_KEYWORD_MATCH = "KEYWORD_MATCH"
RISK_FACTOR_VIRAL_SPREAD = "VIRAL_SPREAD"

__all__ = [
    # ... existing exports ...
    # Phase 4 exports
    "ENGAGEMENT_WEIGHT_LIKE",
    "ENGAGEMENT_WEIGHT_COMMENT",
    "ENGAGEMENT_WEIGHT_SHARE",
    "ENGAGEMENT_MIN_VIEWS_FOR_NORMALIZATION",
    "ENGAGEMENT_SCORE_CAP",
    "VIRALITY_DENOMINATOR_OFFSET",
    "INFLUENCE_FOLLOWER_DIVISOR",
    "CRISIS_KEYWORDS",
    "RISK_SENTIMENT_NEGATIVE_THRESHOLD",
    "RISK_SENTIMENT_EXTREME_THRESHOLD",
    "RISK_KEYWORD_WEIGHT",
    "RISK_SENTIMENT_BASE_WEIGHT",
    "RISK_SENTIMENT_EXTREME_WEIGHT",
    "RISK_VIRALITY_AMPLIFIER_THRESHOLD",
    "RISK_VIRALITY_AMPLIFIER_MIN_BASE",
    "RISK_SCORE_CRITICAL_THRESHOLD",
    "RISK_SCORE_HIGH_THRESHOLD",
    "RISK_SCORE_MEDIUM_THRESHOLD",
    "RISK_FACTOR_NEGATIVE_SENTIMENT",
    "RISK_FACTOR_EXTREME_NEGATIVE",
    "RISK_FACTOR_KEYWORD_MATCH",
    "RISK_FACTOR_VIRAL_SPREAD",
]
```

---

### 2.2 `internal/impact_calculation/type.py` — Thêm Output Fields

Sửa `Output` dataclass:

```python
@dataclass
class Output:
    """Output of impact calculation."""

    impact_score: float
    risk_level: str
    is_viral: bool
    is_kol: bool
    impact_breakdown: ImpactBreakdown

    # === PHASE 4: NEW FIELDS ===
    engagement_score: float = 0.0
    virality_score: float = 0.0
    influence_score: float = 0.0
    risk_factors: list[dict[str, Any]] = field(default_factory=list)
```

Thêm vào `__all__`:

```python
__all__ = [
    # ... existing ...
    "Output",  # Already there, just ensure it includes new fields
]
```

---

### 2.3 `internal/impact_calculation/usecase/impact_calculation.py` — Implement Phase 4 Logic

**Thêm 3 methods mới:**

```python
    def calculate_engagement_score(
        self,
        likes: int,
        comments: int,
        shares: int,
        views: int
    ) -> float:
        """Calculate engagement score.

        Formula: (likes*1 + comments*2 + shares*3) / views * 100
        Cap at 100. If views < 100, use raw weighted sum.

        Args:
            likes: Number of likes
            comments: Number of comments
            shares: Number of shares
            views: Number of views

        Returns:
            Engagement score (0-100)
        """
        likes = max(0, likes)
        comments = max(0, comments)
        shares = max(0, shares)
        views = max(0, views)

        weighted_sum = (
            likes * ENGAGEMENT_WEIGHT_LIKE +
            comments * ENGAGEMENT_WEIGHT_COMMENT +
            shares * ENGAGEMENT_WEIGHT_SHARE
        )

        if views >= ENGAGEMENT_MIN_VIEWS_FOR_NORMALIZATION:
            score = (weighted_sum / views) * 100
        else:
            # Low volume — use raw score
            score = weighted_sum

        return min(score, ENGAGEMENT_SCORE_CAP)

    def calculate_virality_score(
        self,
        likes: int,
        comments: int,
        shares: int
    ) -> float:
        """Calculate virality score.

        Formula: shares / (likes + comments + 1)

        Args:
            likes: Number of likes
            comments: Number of comments
            shares: Number of shares

        Returns:
            Virality score (0-1+)
        """
        likes = max(0, likes)
        comments = max(0, comments)
        shares = max(0, shares)

        denominator = likes + comments + VIRALITY_DENOMINATOR_OFFSET
        return shares / denominator

    def calculate_influence_score(
        self,
        followers: int,
        engagement_score: float
    ) -> float:
        """Calculate influence score.

        Formula: (followers / 1M) * engagement_score

        Args:
            followers: Author follower count
            engagement_score: Calculated engagement score

        Returns:
            Influence score
        """
        followers = max(0, followers)
        normalized_followers = followers / INFLUENCE_FOLLOWER_DIVISOR
        return normalized_followers * engagement_score
```

**Nâng cấp `_calculate_risk()` method:**

```python
    def _calculate_risk(
        self,
        impact_score: float,
        sentiment_label: str,
        sentiment_score: float,
        is_kol: bool,
        text: str,
        virality_score: float
    ) -> tuple[str, float, list[dict[str, Any]]]:
        """Classify risk level using multi-factor assessment.

        Phase 4 upgrade: Add crisis keywords + virality amplifier.

        Args:
            impact_score: Calculated impact score
            sentiment_label: Sentiment label (POSITIVE/NEUTRAL/NEGATIVE)
            sentiment_score: Sentiment score (-1 to 1)
            is_kol: Whether author is KOL
            text: Post text content
            virality_score: Calculated virality score

        Returns:
            Tuple of (risk_level, risk_score, risk_factors)
        """
        label = (sentiment_label or "").strip().upper()
        risk_score = 0.0
        risk_factors = []

        # Factor 1: Sentiment Impact
        if sentiment_score < RISK_SENTIMENT_NEGATIVE_THRESHOLD:
            risk_score += RISK_SENTIMENT_BASE_WEIGHT
            risk_factors.append({
                "factor": RISK_FACTOR_NEGATIVE_SENTIMENT,
                "severity": "MEDIUM",
                "description": f"Negative sentiment detected (score: {sentiment_score:.2f})"
            })

        if sentiment_score < RISK_SENTIMENT_EXTREME_THRESHOLD:
            risk_score += RISK_SENTIMENT_EXTREME_WEIGHT
            risk_factors.append({
                "factor": RISK_FACTOR_EXTREME_NEGATIVE,
                "severity": "HIGH",
                "description": f"Extreme negative sentiment (score: {sentiment_score:.2f})"
            })

        # Factor 2: Crisis Keywords
        text_lower = text.lower() if text else ""
        matched_keywords = []
        for keyword in CRISIS_KEYWORDS:
            if keyword in text_lower:
                matched_keywords.append(keyword)

        if matched_keywords:
            risk_score += RISK_KEYWORD_WEIGHT
            risk_factors.append({
                "factor": RISK_FACTOR_KEYWORD_MATCH,
                "severity": "HIGH",
                "description": f"Crisis keywords detected: {', '.join(matched_keywords)}"
            })

        # Factor 3: Virality Amplifier
        if (risk_score >= RISK_VIRALITY_AMPLIFIER_MIN_BASE and
            virality_score > RISK_VIRALITY_AMPLIFIER_THRESHOLD):
            amplifier = 1 + virality_score
            risk_score *= amplifier
            risk_factors.append({
                "factor": RISK_FACTOR_VIRAL_SPREAD,
                "severity": "CRITICAL",
                "description": f"High virality amplifying risk (virality: {virality_score:.2f}, amplifier: {amplifier:.2f}x)"
            })

        # Classification
        if risk_score >= RISK_SCORE_CRITICAL_THRESHOLD:
            return RISK_CRITICAL, risk_score, risk_factors
        if risk_score >= RISK_SCORE_HIGH_THRESHOLD:
            return RISK_HIGH, risk_score, risk_factors
        if risk_score >= RISK_SCORE_MEDIUM_THRESHOLD:
            return RISK_MEDIUM, risk_score, risk_factors

        return RISK_LOW, risk_score, risk_factors
```

**Update `process()` method để gọi Phase 4 calculations:**

```python
    def process(self, input_data: Input) -> Output:
        """Process input data and return output.

        Phase 4: Add engagement_score, virality_score, influence_score calculations.
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[ImpactCalculation] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:
            if self.logger:
                self.logger.debug(
                    "[ImpactCalculation] Processing started",
                    extra={
                        "platform": input_data.platform,
                        "followers": input_data.author.followers,
                        "sentiment": input_data.sentiment.label,
                    },
                )

            # === PHASE 4: NEW CALCULATIONS ===

            # 1. Engagement Score
            engagement_score = self.calculate_engagement_score(
                likes=input_data.interaction.likes,
                comments=input_data.interaction.comments_count,
                shares=input_data.interaction.shares,
                views=input_data.interaction.views
            )

            # 2. Virality Score
            virality_score = self.calculate_virality_score(
                likes=input_data.interaction.likes,
                comments=input_data.interaction.comments_count,
                shares=input_data.interaction.shares
            )

            # 3. Influence Score
            influence_score = self.calculate_influence_score(
                followers=input_data.author.followers,
                engagement_score=engagement_score
            )

            # === EXISTING CALCULATIONS (keep) ===

            # Calculate reach score (existing)
            reach_score = self._calculate_reach(input_data.author)

            # Get multipliers (existing)
            platform_multiplier = self._get_platform_multiplier(input_data.platform)
            sentiment_amplifier = self._get_sentiment_amplifier(
                input_data.sentiment.label
            )

            # Calculate raw impact (existing)
            raw_impact = (
                engagement_score  # Use new engagement_score instead of old _calculate_engagement
                * reach_score
                * platform_multiplier
                * sentiment_amplifier
            )

            # Normalize to 0-100 (existing)
            impact_score = self._normalize_impact(raw_impact)

            # Determine flags (existing)
            is_kol = input_data.author.followers >= self.config.kol_follower_threshold
            is_viral = impact_score >= self.config.viral_threshold

            # === PHASE 4: UPGRADED RISK CALCULATION ===

            # Get text content for keyword matching
            text = getattr(input_data, 'text', '') or ''

            risk_level, risk_score, risk_factors = self._calculate_risk(
                impact_score=impact_score,
                sentiment_label=input_data.sentiment.label,
                sentiment_score=input_data.sentiment.score,
                is_kol=is_kol,
                text=text,
                virality_score=virality_score
            )

            # Build breakdown (existing)
            breakdown = ImpactBreakdown(
                engagement_score=engagement_score,
                reach_score=reach_score,
                platform_multiplier=platform_multiplier,
                sentiment_amplifier=sentiment_amplifier,
                raw_impact=raw_impact,
            )

            if self.logger:
                self.logger.info(
                    "[ImpactCalculation] Processing completed",
                    extra={
                        "impact_score": impact_score,
                        "risk_level": risk_level,
                        "risk_score": risk_score,
                        "is_viral": is_viral,
                        "is_kol": is_kol,
                        "engagement_score": engagement_score,
                        "virality_score": virality_score,
                        "influence_score": influence_score,
                    },
                )

            return Output(
                impact_score=impact_score,
                risk_level=risk_level,
                is_viral=is_viral,
                is_kol=is_kol,
                impact_breakdown=breakdown,
                # Phase 4 fields
                engagement_score=engagement_score,
                virality_score=virality_score,
                influence_score=influence_score,
                risk_factors=risk_factors,
            )

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[ImpactCalculation] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise
```

**Lưu ý:** Xoá method `_calculate_engagement()` cũ vì giờ dùng `calculate_engagement_score()` public method.

---

### 2.4 `internal/text_preprocessing/constant.py` — Thêm Spam Detection Constants

Thêm vào cuối file:

```python
# === PHASE 4: SPAM DETECTION ===

# Spam Detection Thresholds
MIN_TEXT_LENGTH = 5
MIN_WORD_DIVERSITY = 0.3  # distinct_words / total_words

# Ads Keywords (Vietnamese + English)
ADS_KEYWORDS = [
    "mua ngay", "giảm giá", "khuyến mãi", "sale off",
    "click link", "inbox", "đặt hàng", "liên hệ ngay",
    "giá sốc", "hot deal", "freeship", "miễn phí vận chuyển",
]

__all__ = [
    # ... existing exports ...
    # Phase 4 exports
    "MIN_TEXT_LENGTH",
    "MIN_WORD_DIVERSITY",
    "ADS_KEYWORDS",
]
```

---

### 2.5 `internal/text_preprocessing/type.py` — Thêm Spam Detection Output

Sửa `Output` dataclass:

```python
@dataclass
class Output:
    """Output of text preprocessing."""

    cleaned_text: str
    original_text: str

    # === PHASE 4: NEW FIELDS ===
    is_spam: bool = False
    spam_reasons: list[str] = field(default_factory=list)
```

---

### 2.6 `internal/text_preprocessing/usecase/preprocessing.py` — Implement Spam Detection

Thêm method mới:

```python
    def detect_spam(self, text: str) -> tuple[bool, list[str]]:
        """Detect spam using heuristics.

        Rules:
        1. Text too short (< 5 chars)
        2. Low word diversity (< 30%)
        3. Contains ads keywords

        Args:
            text: Text to check

        Returns:
            Tuple of (is_spam, reasons)
        """
        if not text or not isinstance(text, str):
            return False, []

        reasons = []

        # Rule 1: Too short
        if len(text.strip()) < MIN_TEXT_LENGTH:
            reasons.append("TEXT_TOO_SHORT")

        # Rule 2: Low word diversity
        words = text.split()
        if len(words) > 0:
            distinct_words = len(set(words))
            diversity = distinct_words / len(words)
            if diversity < MIN_WORD_DIVERSITY:
                reasons.append(f"LOW_WORD_DIVERSITY_{diversity:.2f}")

        # Rule 3: Ads keywords
        text_lower = text.lower()
        matched_ads = []
        for keyword in ADS_KEYWORDS:
            if keyword in text_lower:
                matched_ads.append(keyword)

        if matched_ads:
            reasons.append(f"ADS_KEYWORDS_{','.join(matched_ads)}")

        is_spam = len(reasons) > 0

        if self.logger and is_spam:
            self.logger.debug(
                "[TextPreprocessing] Spam detected",
                extra={"reasons": reasons}
            )

        return is_spam, reasons
```

Update `process()` method để gọi spam detection:

```python
    def process(self, input_data: Input) -> Output:
        """Process text preprocessing.

        Phase 4: Add spam detection.
        """
        text = input_data.text

        # Existing cleaning logic
        cleaned = self._clean_text(text)

        # === PHASE 4: SPAM DETECTION ===
        is_spam, spam_reasons = self.detect_spam(text)

        return Output(
            cleaned_text=cleaned,
            original_text=text,
            is_spam=is_spam,
            spam_reasons=spam_reasons,
        )
```

---

### 2.7 `internal/analytics/type.py` — Update AnalyticsResult

Thêm Phase 4 fields vào `AnalyticsResult` dataclass:

```python
@dataclass
class AnalyticsResult:
    """Analytics result data structure."""

    # ... existing fields ...

    # === PHASE 4: NEW FIELDS ===
    engagement_score: float = 0.0
    virality_score: float = 0.0
    influence_score: float = 0.0
    risk_factors: list[dict[str, Any]] = field(default_factory=list)
    spam_reasons: list[str] = field(default_factory=list)
```

Update `to_dict()` method:

```python
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for repository."""
        return {
            # ... all existing fields ...
            "processing_status": self.processing_status,

            # === PHASE 4: NEW FIELDS ===
            "engagement_score": self.engagement_score,
            "virality_score": self.virality_score,
            "influence_score": self.influence_score,
            "risk_factors": self.risk_factors,
            "spam_reasons": self.spam_reasons,
        }
```

---

### 2.8 `internal/analytics/usecase/usecase.py` — Integrate Phase 4 Calculations

Update `_run_pipeline()` method:

```python
    def _run_pipeline(self, enriched_post_data: EnrichedPostData) -> AnalyticsResult:
        """Run the full analytics pipeline.

        Phase 4: Integrate engagement, virality, influence, spam detection.
        """
        meta = enriched_post_data.meta
        content = enriched_post_data.content
        interaction = enriched_post_data.interaction
        author = enriched_post_data.author

        post_id = meta.get("id")
        platform = self._normalize_platform(meta.get("platform"))

        # Extract text for analysis
        text = content.get("text") or content.get("description") or ""
        transcription = content.get("transcription") or ""
        full_text = f"{text} {transcription}".strip()

        # Initialize result with base data
        import uuid

        result = AnalyticsResult(
            id=str(uuid.uuid4()),
            project_id=meta.get("project_id"),
            source_id=str(meta.get("id")) if meta.get("id") else None,
            platform=platform,
            published_at=meta.get("published_at") or datetime.now(timezone.utc),
            analyzed_at=datetime.now(timezone.utc),
            model_version=self.config.model_version,
        )

        # Add raw metrics
        views = self._safe_int(interaction.get("views"))
        likes = self._safe_int(interaction.get("likes"))
        comments = self._safe_int(interaction.get("comments_count"))
        shares = self._safe_int(interaction.get("shares"))
        saves = self._safe_int(interaction.get("saves"))
        followers = self._safe_int(author.get("followers"))

        result.view_count = views
        result.like_count = likes
        result.comment_count = comments
        result.share_count = shares
        result.save_count = saves
        result.follower_count = followers

        # Add crawler metadata
        self._add_crawler_metadata(result, meta, content, author)

        # === STAGE 1: PREPROCESSING (Phase 4: Add spam detection) ===
        if self.config.enable_preprocessing and self.preprocessor:
            from internal.text_preprocessing.type import Input as PreprocessInput

            preprocess_output = self.preprocessor.process(
                PreprocessInput(text=full_text)
            )

            # Store spam detection results
            if preprocess_output.is_spam:
                result.is_spam = True
                result.spam_reasons = preprocess_output.spam_reasons

                if self.logger:
                    self.logger.info(
                        f"[Pipeline] Spam detected: {post_id}, reasons: {preprocess_output.spam_reasons}"
                    )

        # === STAGE 2: INTENT CLASSIFICATION ===
        if self.config.enable_intent_classification and self.intent_classifier:
            # TODO: Implement intent classification
            # Check if should skip (spam/seeding)
            pass

        # === STAGE 3: KEYWORD EXTRACTION ===
        keywords = []
        if self.config.enable_keyword_extraction and self.keyword_extractor:
            # TODO: Implement keyword extraction
            pass

        # === STAGE 4: SENTIMENT ANALYSIS ===
        sentiment_label = "NEUTRAL"
        sentiment_score = 0.0

        if self.config.enable_sentiment_analysis and self.sentiment_analyzer:
            # TODO: Implement sentiment analysis
            # For now, use defaults
            pass

        # === STAGE 5: IMPACT CALCULATION (Phase 4: Add new metrics) ===
        if self.config.enable_impact_calculation and self.impact_calculator:
            from internal.impact_calculation.type import (
                Input as ImpactInput,
                InteractionInput,
                AuthorInput,
                SentimentInput,
            )

            impact_input = ImpactInput(
                interaction=InteractionInput(
                    views=views,
                    likes=likes,
                    comments_count=comments,
                    shares=shares,
                    saves=saves,
                ),
                author=AuthorInput(
                    followers=followers,
                    is_verified=author.get("is_verified", False),
                ),
                sentiment=SentimentInput(
                    label=sentiment_label,
                    score=sentiment_score,
                ),
                platform=platform,
            )

            # Add text field for risk assessment keyword matching
            impact_input.text = full_text

            impact_output = self.impact_calculator.process(impact_input)

            # Map to result
            result.impact_score = impact_output.impact_score
            result.risk_level = impact_output.risk_level
            result.is_viral = impact_output.is_viral
            result.is_kol = impact_output.is_kol

            # === PHASE 4: NEW FIELDS ===
            result.engagement_score = impact_output.engagement_score
            result.virality_score = impact_output.virality_score
            result.influence_score = impact_output.influence_score
            result.risk_factors = impact_output.risk_factors

        return result
```

**Lưu ý:** Cần thêm `text` field vào `ImpactInput` type để pass text cho risk assessment. Sửa `internal/impact_calculation/type.py`:

```python
@dataclass
class Input:
    """Input structure for impact calculation."""

    interaction: InteractionInput
    author: AuthorInput
    sentiment: SentimentInput
    platform: str = PLATFORM_UNKNOWN
    text: str = ""  # Phase 4: For risk keyword matching
```

---

### 2.9 `internal/analyzed_post/repository/postgre/helpers.py` — Update Transform

Update `transform_to_post_analytics()` để map Phase 4 fields:

```python
def transform_to_post_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform AnalyticsResult dict → post_analytics columns.

    Phase 4: Map engagement_score, virality_score, influence_score, risk_factors.
    """
    now = datetime.now(timezone.utc)

    # Build uap_metadata JSONB
    uap_metadata = _build_uap_metadata(data)

    # Build aspects JSONB from aspects_breakdown
    aspects = _extract_aspects(data.get("aspects_breakdown", {}))

    # Derive risk_score from risk_level
    risk_level = data.get("risk_level", "LOW")
    risk_score = _risk_level_to_score(risk_level)

    # Derive flags
    primary_intent = data.get("primary_intent", "DISCUSSION")

    # === PHASE 4: is_spam from spam detection, not just intent ===
    is_spam_from_intent = primary_intent in ("SPAM", "SEEDING")
    is_spam_from_detection = data.get("is_spam", False)
    is_spam = is_spam_from_intent or is_spam_from_detection

    requires_attention = risk_level in ("HIGH", "CRITICAL")

    return {
        "id": _get_or_generate_id(data),
        "project_id": data.get("project_id", ""),
        "source_id": data.get("source_id"),
        "content": data.get("content_text", ""),
        "content_created_at": _parse_datetime(data.get("published_at")),
        "ingested_at": _parse_datetime(data.get("crawled_at")),
        "platform": (data.get("platform") or "UNKNOWN").lower(),
        "uap_metadata": uap_metadata,
        "overall_sentiment": data.get("overall_sentiment", "NEUTRAL"),
        "overall_sentiment_score": data.get("overall_sentiment_score", 0.0),
        "sentiment_confidence": data.get("overall_confidence", 0.0),
        "sentiment_explanation": None,  # Future
        "aspects": aspects,
        "keywords": data.get("keywords", []),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": data.get("risk_factors", []),  # Phase 4
        "requires_attention": requires_attention,
        "alert_triggered": False,

        # === PHASE 4: NEW METRICS ===
        "engagement_score": data.get("engagement_score", 0.0),
        "virality_score": data.get("virality_score", 0.0),
        "influence_score": data.get("influence_score", 0.0),

        "reach_estimate": data.get("view_count", 0),
        "content_quality_score": 0.0,  # Future
        "is_spam": is_spam,
        "is_bot": False,  # Future
        "language": None,  # Future
        "language_confidence": 0.0,  # Future
        "toxicity_score": 0.0,  # Future
        "is_toxic": False,  # Future
        "primary_intent": primary_intent,
        "intent_confidence": data.get("intent_confidence", 0.0),
        "impact_score": data.get("impact_score", 0.0),
        "processing_time_ms": data.get("processing_time_ms", 0),
        "model_version": data.get("model_version", "1.0.0"),
        "processing_status": data.get("processing_status", "success"),
        "analyzed_at": _parse_datetime(data.get("analyzed_at")) or now,
        "indexed_at": None,
        "created_at": now,
        "updated_at": now,
    }
```

---

## 3. DATA FLOW (Phase 4)

```
Pipeline.process(Input)
    │
    ├── Stage 1: TextPreprocessing
    │   └── detect_spam(text) → is_spam, spam_reasons
    │
    ├── Stage 2: IntentClassification (existing)
    │
    ├── Stage 3: KeywordExtraction (existing)
    │
    ├── Stage 4: SentimentAnalysis (existing)
    │
    ├── Stage 5: ImpactCalculation (Phase 4 upgrade)
    │   ├── calculate_engagement_score(likes, comments, shares, views)
    │   ├── calculate_virality_score(likes, comments, shares)
    │   ├── calculate_influence_score(followers, engagement_score)
    │   └── _calculate_risk(sentiment, text, virality) → risk_level, risk_score, risk_factors
    │
    ├── Build AnalyticsResult with Phase 4 fields
    │
    ├── analyzed_post_usecase.create(result.to_dict())
    │   └── transform_to_post_analytics(data)
    │       → INSERT INTO analytics.post_analytics (with Phase 4 columns)
    │
    └── Return Output
```

---

## 4. FORMULAS SUMMARY

### 4.1 Engagement Score

```
engagement_score = (likes*1 + comments*2 + shares*3) / views * 100

If views < 100:
    engagement_score = likes*1 + comments*2 + shares*3  (raw)

Cap at 100
```

### 4.2 Virality Score

```
virality_score = shares / (likes + comments + 1)
```

### 4.3 Influence Score

```
influence_score = (followers / 1_000_000) * engagement_score
```

### 4.4 Risk Assessment

```
risk_score = 0.0
risk_factors = []

# Factor 1: Sentiment
if sentiment_score < -0.3:
    risk_score += 0.3
    risk_factors.append("NEGATIVE_SENTIMENT")

if sentiment_score < -0.7:
    risk_score += 0.2
    risk_factors.append("EXTREME_NEGATIVE")

# Factor 2: Crisis Keywords
if any(keyword in text for keyword in CRISIS_KEYWORDS):
    risk_score += 0.4
    risk_factors.append("KEYWORD_MATCH")

# Factor 3: Virality Amplifier
if risk_score >= 0.3 and virality_score > 0.1:
    risk_score *= (1 + virality_score)
    risk_factors.append("VIRAL_SPREAD")

# Classification
if risk_score >= 0.8: return "CRITICAL"
if risk_score >= 0.6: return "HIGH"
if risk_score >= 0.3: return "MEDIUM"
return "LOW"
```

### 4.5 Spam Detection

```
is_spam = False
reasons = []

# Rule 1: Too short
if len(text) < 5:
    reasons.append("TEXT_TOO_SHORT")

# Rule 2: Low word diversity
distinct_words = len(set(words))
diversity = distinct_words / len(words)
if diversity < 0.3:
    reasons.append("LOW_WORD_DIVERSITY")

# Rule 3: Ads keywords
if any(keyword in text for keyword in ADS_KEYWORDS):
    reasons.append("ADS_KEYWORDS")

is_spam = len(reasons) > 0
```

---

## 5. FIELD MAPPING: Phase 4 Calculations → DB

| Calculation Output                 | AnalyticsResult field | post_analytics column | Logic                                   |
| ---------------------------------- | --------------------- | --------------------- | --------------------------------------- |
| `calculate_engagement_score()`     | `engagement_score`    | `engagement_score`    | Direct copy                             |
| `calculate_virality_score()`       | `virality_score`      | `virality_score`      | Direct copy                             |
| `calculate_influence_score()`      | `influence_score`     | `influence_score`     | Direct copy                             |
| `_calculate_risk()` → risk_factors | `risk_factors`        | `risk_factors`        | JSONB array of {factor, severity, desc} |
| `detect_spam()` → is_spam          | `is_spam`             | `is_spam`             | OR with intent-based spam               |
| `detect_spam()` → spam_reasons     | `spam_reasons`        | —                     | Stored in uap_metadata (optional)       |

---

## 6. TESTING STRATEGY

### 6.1 Unit Tests

| Test                                  | File                               | Mô tả                                                     |
| ------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| `test_calculate_engagement_score`     | `tests/test_impact_calculation.py` | Test với views >= 100, views < 100, all zeros, cap at 100 |
| `test_calculate_virality_score`       | `tests/test_impact_calculation.py` | Test division safety, zero denominator                    |
| `test_calculate_influence_score`      | `tests/test_impact_calculation.py` | Test với followers = 0, 50k, 1M, 10M                      |
| `test_calculate_risk_negative`        | `tests/test_impact_calculation.py` | Test sentiment < -0.3, < -0.7                             |
| `test_calculate_risk_keywords`        | `tests/test_impact_calculation.py` | Test crisis keywords matching                             |
| `test_calculate_risk_viral_amplifier` | `tests/test_impact_calculation.py` | Test virality amplifier logic                             |
| `test_detect_spam_short_text`         | `tests/test_preprocessing.py`      | Test text < 5 chars                                       |
| `test_detect_spam_low_diversity`      | `tests/test_preprocessing.py`      | Test repetitive text                                      |
| `test_detect_spam_ads_keywords`       | `tests/test_preprocessing.py`      | Test ads keywords matching                                |
| `test_transform_phase4_fields`        | `tests/test_helpers.py`            | Verify Phase 4 fields mapping                             |

### 6.2 Integration Tests

1. Send UAP message → verify `engagement_score`, `virality_score`, `influence_score` trong DB
2. Send post với crisis keywords → verify `risk_factors` JSONB
3. Send spam post → verify `is_spam = true`
4. Send viral negative post → verify risk amplification
5. Query `risk_factors @> '[{"factor": "KEYWORD_MATCH"}]'` → verify GIN index

### 6.3 Edge Cases

| Case                              | Expected Behavior                            |
| --------------------------------- | -------------------------------------------- |
| views = 0                         | engagement_score = raw weighted sum          |
| All metrics = 0                   | engagement_score = 0, virality_score = 0     |
| shares = 1000, likes+comments = 0 | virality_score = 1000 (high)                 |
| followers = 0                     | influence_score = 0                          |
| Text = ""                         | is_spam = False (no spam detection on empty) |
| Text = "a"                        | is_spam = True (TEXT_TOO_SHORT)              |
| Text = "mua mua mua mua"          | is_spam = True (LOW_WORD_DIVERSITY)          |
| Text = "mua ngay giảm giá"        | is_spam = True (ADS_KEYWORDS)                |
| Sentiment = -0.8, virality = 0.5  | risk_score amplified, VIRAL_SPREAD factor    |
| Text contains "lừa đảo" + "cháy"  | risk_score += 0.4 (only first match counts)  |

---

## 7. DEPENDENCY GRAPH

```
internal/impact_calculation/constant.py          ← MODIFIED (add Phase 4 constants)
internal/impact_calculation/type.py              ← MODIFIED (add Phase 4 output fields)
    ↑
internal/impact_calculation/usecase/impact_calculation.py  ← MODIFIED (add 3 methods + upgrade risk)
    ↑
internal/text_preprocessing/constant.py          ← MODIFIED (add spam constants)
internal/text_preprocessing/type.py              ← MODIFIED (add spam output fields)
    ↑
internal/text_preprocessing/usecase/preprocessing.py  ← MODIFIED (add detect_spam method)
    ↑
internal/analytics/type.py                       ← MODIFIED (add Phase 4 fields to AnalyticsResult)
    ↑
internal/analytics/usecase/usecase.py            ← MODIFIED (integrate Phase 4 calculations)
    ↑
internal/analyzed_post/repository/postgre/helpers.py  ← MODIFIED (map Phase 4 fields)
```

**Thứ tự implement:**

1. `internal/impact_calculation/constant.py` (thêm constants)
2. `internal/impact_calculation/type.py` (thêm output fields + text input field)
3. `internal/impact_calculation/usecase/impact_calculation.py` (implement 3 methods + upgrade risk)
4. `internal/text_preprocessing/constant.py` (thêm spam constants)
5. `internal/text_preprocessing/type.py` (thêm spam output fields)
6. `internal/text_preprocessing/usecase/preprocessing.py` (implement detect_spam)
7. `internal/analytics/type.py` (thêm Phase 4 fields vào AnalyticsResult + to_dict)
8. `internal/analytics/usecase/usecase.py` (integrate vào pipeline)
9. `internal/analyzed_post/repository/postgre/helpers.py` (update transform)
10. Write unit tests
11. Run integration tests

---

## 8. CONVENTION ADHERENCE

### 8.1 Domain Layer (impact_calculation, text_preprocessing)

- **Usecase:** Pure business logic, framework-agnostic
- **Type:** Dataclasses cho Input/Output, không có business logic
- **Constant:** Tất cả magic numbers thành named constants
- **Interface:** Protocol với `@runtime_checkable`
- **Errors:** Prefix `Err`, inherit từ base exception

### 8.2 Code Style

- **Method naming:** `calculate_*`, `detect_*`, `evaluate_*` cho business logic
- **Private methods:** Prefix `_` cho internal helpers
- **Type hints:** Đầy đủ cho tất cả parameters và return types
- **Docstrings:** Google style, mô tả formula và edge cases
- **Logging:** Debug level cho intermediate values, Info level cho results

### 8.3 Testing

- **Unit tests:** Test từng method riêng lẻ với edge cases
- **Integration tests:** Test end-to-end pipeline flow
- **Test naming:** `test_<method>_<scenario>`
- **Assertions:** Specific assertions với tolerance cho float comparisons

---

## 9. VERIFICATION CHECKLIST

### 9.1 Implementation

- [ ] Constants added to `impact_calculation/constant.py`
- [ ] Constants added to `text_preprocessing/constant.py`
- [ ] Output types updated with Phase 4 fields
- [ ] `calculate_engagement_score()` implemented
- [ ] `calculate_virality_score()` implemented
- [ ] `calculate_influence_score()` implemented
- [ ] `_calculate_risk()` upgraded with multi-factor logic
- [ ] `detect_spam()` implemented
- [ ] `AnalyticsResult` updated with Phase 4 fields
- [ ] `AnalyticsResult.to_dict()` includes Phase 4 fields
- [ ] Pipeline integrates Phase 4 calculations
- [ ] `transform_to_post_analytics()` maps Phase 4 fields

### 9.2 Testing

- [ ] Unit tests pass for all new methods
- [ ] Edge cases covered (zeros, division by zero, empty text)
- [ ] Integration test: engagement_score in DB
- [ ] Integration test: virality_score in DB
- [ ] Integration test: influence_score in DB
- [ ] Integration test: risk_factors JSONB in DB
- [ ] Integration test: is_spam detection works
- [ ] Integration test: crisis keywords trigger risk factors
- [ ] Integration test: virality amplifier works

### 9.3 Data Quality

- [ ] No NULL values in Phase 4 columns (defaults work)
- [ ] engagement_score capped at 100
- [ ] virality_score >= 0
- [ ] influence_score >= 0
- [ ] risk_factors is valid JSONB array
- [ ] is_spam boolean correct
- [ ] Query performance acceptable with new calculations

### 9.4 Backward Compatibility

- [ ] Existing records (Phase 3) still queryable
- [ ] Phase 4 fields have sensible defaults (0.0, [], False)
- [ ] No breaking changes to existing APIs
- [ ] Pipeline still works if modules disabled

---

## 10. RISKS & MITIGATIONS

| Risk                                       | Impact | Mitigation                                                  |
| ------------------------------------------ | ------ | ----------------------------------------------------------- |
| Division by zero in formulas               | HIGH   | Add safety checks: `max(1, views)`, `denominator + 1`       |
| Crisis keywords false positives            | MEDIUM | Tune keyword list, add context checking in future           |
| Spam detection too aggressive              | MEDIUM | Start with conservative thresholds, monitor false positives |
| Performance impact from text processing    | LOW    | Text operations are fast, crisis keywords list is small     |
| Risk amplifier causing score overflow      | LOW    | Risk score capped by classification thresholds              |
| Engagement score unfair for low-view posts | MEDIUM | Use raw score for views < 100, document behavior            |
| Virality score unbounded                   | LOW    | Document that high values are expected for viral content    |

---

## 11. FUTURE ENHANCEMENTS (Out of Scope)

### 11.1 Language Detection

- Use `langdetect` or `fasttext` library
- Populate `language` and `language_confidence` fields
- Enable language-specific sentiment models

### 11.2 Toxicity Detection

- Integrate toxicity detection model (e.g., Perspective API, local model)
- Populate `toxicity_score` and `is_toxic` fields
- Add toxicity as risk factor

### 11.3 Bot Detection

- Analyze posting patterns (frequency, timing)
- Check account age, follower/following ratio
- Populate `is_bot` field

### 11.4 Content Quality Score

- Analyze text complexity, grammar, coherence
- Check for meaningful content vs noise
- Populate `content_quality_score` field

### 11.5 Sentiment Explanation

- Use explainable AI techniques
- Generate human-readable explanation for sentiment
- Populate `sentiment_explanation` field

### 11.6 Advanced Risk Assessment

- Machine learning model for risk prediction
- Historical pattern analysis
- Network effect analysis (cross-post correlation)

---

## 12. TIMELINE

| Task                                  | Estimate   |
| ------------------------------------- | ---------- |
| Constants + Types                     | 0.5 day    |
| Engagement/Virality/Influence methods | 1 day      |
| Multi-factor Risk Assessment          | 1 day      |
| Spam Detection                        | 0.5 day    |
| Pipeline Integration                  | 1 day      |
| Unit Tests                            | 1 day      |
| Integration Tests                     | 0.5 day    |
| Bug fixes + Edge cases                | 0.5 day    |
| **Total**                             | **6 days** |

---

**END OF PHASE 4 CODE PLAN**
