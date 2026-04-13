# Phase 2 — Pipeline Orchestrator + Runtime

> **Depends on:** Phase 1 (contract publisher cần `run_id`)
> **Module:** `internal/pipeline/`, `internal/runtime/`
> **Source:** `core-analysis/src/smap/pipeline.py`, `run_manifest.py`

## Mục tiêu

Implement orchestrator batch run với `run_id`, thứ tự stage, và runtime utilities.
Sau phase này, analysis-srv có khả năng chạy 1 run đầy đủ: nhận batch → chạy stages → publish 3 topics.

## Folder structure

```
internal/pipeline/
├── interface.py       # IPipelineUseCase
├── type.py            # PipelineInput, PipelineRunResult, StageResult
├── constant.py        # STAGE_* names, feature flags
├── errors.py          # PipelineError, StageTimeoutError
└── usecase/
    ├── new.py
    ├── usecase.py
    ├── run_pipeline.py   # run_pipeline() — main orchestrator
    └── helpers.py        # _run_stage(), _collect_timings()

internal/runtime/
├── interface.py
├── type.py            # RunContext, OntologyConfig, EnumRegistry
├── constant.py
└── usecase/
    ├── new.py
    ├── run_id.py          # default_run_id()
    ├── enum_registry.py   # normalize_enum_value()
    └── run_manifest.py    # build_run_manifest(), summarize_runtime_mode()
```

## `run_id.py`

```python
# Port từ core-analysis/src/smap/run_manifest.py L344
from datetime import datetime, timezone

def default_run_id() -> str:
    """Format: run-YYYYMMDDTHHMMSSz — UTC, ISO-8601 compact."""
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
```

## `enum_registry.py`

```python
# Normalize enum values across pipeline stages

SENTIMENT_LABELS = {"positive", "negative", "neutral", "mixed"}
PLATFORM_UPSTREAM_MAP = {
    "tiktok": "TIKTOK", "facebook": "FACEBOOK",
    "instagram": "INSTAGRAM", "youtube": "YOUTUBE",
}
PLATFORM_DIGEST_MAP = {v: k for k, v in PLATFORM_UPSTREAM_MAP.items()}  # reverse: "TIKTOK" → "tiktok"

def normalize_platform_for_layer3(raw: str) -> str:
    """Layer 3: UPPERCASE."""
    return PLATFORM_UPSTREAM_MAP.get(raw.lower(), raw.upper())

def normalize_platform_for_layer1(raw: str) -> str:
    """Layer 1 (digest): lowercase."""
    return PLATFORM_DIGEST_MAP.get(raw.upper(), raw.lower())

def normalize_sentiment_label(raw: str) -> str:
    norm = raw.upper()
    if norm == "POS": return "POSITIVE"
    if norm == "NEG": return "NEGATIVE"
    if norm == "NEU": return "NEUTRAL"
    return norm if norm in {"POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"} else "NEUTRAL"
```

## `run_pipeline.py` — orchestrator

```python
# Orchestrator tối giản (Phase 2) — stages được enable dần theo feature flags

def run_pipeline(
    batch_input: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineRunResult:
    timings = {}
    facts = PipelineFacts()   # accumulates per-stage outputs

    # Stage sequence — mỗi stage là optional theo feature flag
    stages = [
        ("normalize",    _stage_normalize,    config.enable_normalization),
        ("dedup",        _stage_dedup,        config.enable_dedup),
        ("spam",         _stage_spam,         config.enable_spam),
        ("threads",      _stage_threads,      config.enable_threads),
        ("enrichment",   _stage_enrichment,   config.enable_enrichment),
        ("reporting",    _stage_reporting,    config.enable_reporting),
    ]

    for stage_name, stage_fn, enabled in stages:
        if not enabled:
            continue
        t0 = time.monotonic()
        facts = stage_fn(facts, batch_input, config)
        timings[stage_name] = time.monotonic() - t0

    # Phase 1 compat: nếu reporting chưa có, dùng empty InsightCard list
    insight_cards = facts.insight_cards or []
    bi_bundle = facts.bi_bundle  # None nếu reporting stage chưa implement

    return PipelineRunResult(
        run_id=ctx.run_id,
        insight_cards=insight_cards,
        bi_bundle=bi_bundle,
        nlp_facts=facts.nlp_facts,   # per-document NLP từ enrichment / existing pipeline
        stage_timings=timings,
        total_valid_records=len(batch_input.records),
    )
```

## `PipelineRunResult` → feed vào contract_publisher

```python
@dataclass
class PipelineRunResult:
    run_id: str
    insight_cards: list          # InsightCard[]
    bi_bundle: object | None     # BIReportBundle
    nlp_facts: list              # per-document enriched facts
    stage_timings: dict[str, float]
    total_valid_records: int
```

## Feature flags (Phase 2 defaults)

```python
# internal/pipeline/constant.py
@dataclass
class PipelineConfig:
    enable_normalization: bool = True
    enable_dedup:         bool = False  # Phase 3
    enable_spam:          bool = False  # Phase 3
    enable_threads:       bool = False  # Phase 3
    enable_enrichment:    bool = False  # Phase 4
    enable_reporting:     bool = False  # Phase 5
    # Khi False → stage bị skip, pipeline vẫn chạy với partial data
```

## `run_manifest.py` — port từ core-analysis

```python
# Port từ core-analysis/src/smap/run_manifest.py L150 (summarize_runtime_mode)
# và L348 (build_run_manifest)

def build_run_manifest(
    ctx: RunContext,
    result: PipelineRunResult,
    config: PipelineConfig,
) -> dict:
    return {
        "manifest_version": "2026.04.09-analysis-srv-r1",
        "run_id":           ctx.run_id,
        "generated_at":     utc_now_iso(),
        "total_records":    result.total_valid_records,
        "stage_timings":    result.stage_timings,
        "pipeline_config": {
            "enable_dedup":       config.enable_dedup,
            "enable_enrichment":  config.enable_enrichment,
            "enable_reporting":   config.enable_reporting,
        },
        "insight_card_count": len(result.insight_cards),
    }
```

## Wiring với consumer hiện tại

Consumer hiện tại ở `internal/analytics/delivery/kafka/consumer/` xử lý từng record.
Trong Phase 2, thêm **batch accumulator** để collect records theo `campaign_id` trước khi trigger pipeline:

```
Kafka UAP records  →  BatchAccumulator  →  (khi batch đủ hoặc timeout)  →  run_pipeline()
```

`BatchAccumulator` logic:
- Accumulate records theo `project_id + campaign_id`
- Trigger khi đạt max batch size (e.g. 2000) hoặc max wait time (e.g. 5 phút)
- Thread-safe, sử dụng `asyncio.Queue` hoặc `threading.Queue` tùy consumer loop
