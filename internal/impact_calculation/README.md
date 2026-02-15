# Impact Calculation Domain

Domain xử lý tính toán impact score và risk level cho social media posts.

## Cấu trúc Domain

```
impact_calculation/
├── usecase/              # Tầng nghiệp vụ (Business Logic Layer)
│   ├── impact_calculation.py  # Core business logic
│   ├── new.py            # Factory function
│   └── __init__.py
├── interface.py          # Domain interfaces (contracts)
├── type.py              # Domain types (data structures)
├── constant.py          # Domain constants
└── README.md            # Documentation
```

**Lưu ý:** Domain này KHÔNG có Delivery Layer và Repository Layer vì:

- Không nhận input trực tiếp từ RabbitMQ/HTTP (không có delivery)
- Không truy cập database (không có repository)
- Chỉ là utility domain được sử dụng bởi các domain khác

## Approach: Impact & Risk Calculation

### 1. Engagement Score
Weighted sum of interactions:
```
EngagementScore = views × 0.01 + likes × 1.0 + comments × 2.0 + saves × 3.0 + shares × 5.0
```

### 2. Reach Score
Logarithmic scale with verified bonus:
```
ReachScore = log10(followers + 1) × (1.2 if verified else 1.0)
```

### 3. Platform Multiplier
- TikTok: 1.0
- Facebook: 1.2
- YouTube: 1.5
- Instagram: 1.1
- Unknown: 1.0

### 4. Sentiment Amplifier
- Negative: 1.5
- Neutral: 1.0
- Positive: 1.1

### 5. Raw Impact
```
RawImpact = EngagementScore × ReachScore × PlatformMultiplier × SentimentAmplifier
```

### 6. Impact Score (0-100)
```
ImpactScore = min(100, (RawImpact / MaxRawScoreCeiling) × 100)
```

### 7. Risk Matrix
| Impact | Sentiment | KOL | Risk Level |
|--------|-----------|-----|------------|
| High (≥70) | Negative | Yes | CRITICAL |
| High (≥70) | Negative | No | HIGH |
| Medium (40-70) | Negative | - | MEDIUM |
| High (≥60) | Neutral/Positive | - | MEDIUM |
| Other | - | - | LOW |

## Cách sử dụng

### 1. Sử dụng trực tiếp

```python
from internal.impact_calculation import New, Config, Input, InteractionInput, AuthorInput, SentimentInput

# Initialize impact calculation
config = Config(
    viral_threshold=70.0,
    kol_follower_threshold=50000,
    max_raw_score_ceiling=100000.0
)
impact_calculation = New(config)

# Calculate impact
input_data = Input(
    interaction=InteractionInput(
        views=10000,
        likes=500,
        comments_count=50,
        shares=20,
        saves=10
    ),
    author=AuthorInput(
        followers=100000,
        is_verified=True
    ),
    sentiment=SentimentInput(
        label="NEGATIVE",
        score=-0.8
    ),
    platform="TIKTOK"
)

output = impact_calculation.process(input_data)
print(f"Impact: {output.impact_score:.2f}")
print(f"Risk: {output.risk_level}")
print(f"Viral: {output.is_viral}")
print(f"KOL: {output.is_kol}")
```

### 2. Sử dụng trong Domain khác

```python
# Trong analytics domain
from internal.impact_calculation import New as NewImpactCalculation, Config as ImpactConfig

class AnalyticsUseCase:
    def __init__(self, deps: Dependencies):
        # Initialize impact calculation with config from dependencies
        impact_config = ImpactConfig(
            viral_threshold=deps.config.impact.threshold.viral,
            kol_follower_threshold=deps.config.impact.threshold.kol_followers,
            max_raw_score_ceiling=deps.config.impact.threshold.max_raw_score,
        )
        self.impact_calculation = NewImpactCalculation(impact_config, deps.logger)

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        # Prepare input
        impact_input = Input(
            interaction=InteractionInput(...),
            author=AuthorInput(...),
            sentiment=SentimentInput(...),
            platform=data["platform"]
        )
        
        # Calculate impact
        impact_output = self.impact_calculation.process(impact_input)
        
        # Use results
        print(f"Impact: {impact_output.impact_score}")
        print(f"Risk: {impact_output.risk_level}")
```

## Flags

### is_viral
Post is viral if `impact_score >= viral_threshold` (default: 70.0)

### is_kol
Author is KOL if `followers >= kol_follower_threshold` (default: 50,000)

## Best Practices

1. **Separation of Concerns:** Mỗi layer có trách nhiệm riêng biệt
2. **Dependency Inversion:** Tầng trong không phụ thuộc tầng ngoài
3. **Reusability:** Use Case có thể dùng cho nhiều delivery methods
4. **Testability:** Dễ test từng layer độc lập
5. **Type Safety:** Sử dụng dataclass thay vì `Dict[str, Any]`
6. **Constants Management:** Tất cả magic strings trong `constant.py`
7. **Factory Pattern:** Sử dụng `New()` để tạo instances
8. **Logger Injection:** Logger là optional, pass từ Dependencies

## Naming Convention

- **Use Case**: `ImpactCalculation`
- **Factory**: `New(config: Config, logger: Optional[Logger] = None) -> ImpactCalculation`
- **Output**: `Output` (KHÔNG dùng `Result`)
- **Method**: `process()` (KHÔNG dùng `calculate()`)
- **Config**: `Config`
- **Interface**: `IImpactCalculation`

## Tham khảo

- Clean Architecture: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design: https://martinfowler.com/bliki/DomainDrivenDesign.html
- Golang project structure: https://github.com/golang-standards/project-layout
