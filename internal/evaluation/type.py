from dataclasses import dataclass, field


@dataclass
class EvalExpected:
    intent: str | None = None
    sentiment: str | None = None
    keywords: list[str] = field(default_factory=list)
    aspects: list[str] = field(default_factory=list)


@dataclass
class EvalSample:
    id: str
    text: str
    expected: EvalExpected


@dataclass
class EvalPrediction:
    intent: str | None = None
    intent_confidence: float | None = None
    sentiment: str | None = None
    sentiment_confidence: float | None = None
    keywords: list[str] = field(default_factory=list)
    aspects: list[str] = field(default_factory=list)
    clean_text: str = ""
    is_spam: bool = False
    spam_reasons: list[str] = field(default_factory=list)


@dataclass
class EvalSampleResult:
    sample_id: str
    expected: EvalExpected
    predicted: EvalPrediction


@dataclass
class MetricCounts:
    correct: int = 0
    total: int = 0


@dataclass
class KeywordCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0


@dataclass
class EvalSummary:
    samples: int
    intent: MetricCounts
    sentiment: MetricCounts
    keywords: KeywordCounts
    aspects: KeywordCounts


__all__ = [
    "EvalExpected",
    "EvalSample",
    "EvalPrediction",
    "EvalSampleResult",
    "MetricCounts",
    "KeywordCounts",
    "EvalSummary",
]
