import json
import os
from pathlib import Path
from typing import Iterable

from config.config import Config, ConfigLoader
from internal.intent_classification.type import Input as IntentInput
from internal.keyword_extraction.type import Input as KeywordInput
from internal.sentiment_analysis.type import Input as SentimentInput, KeywordInput as SAKeywordInput
from internal.text_preprocessing.type import ContentInput, Input as PreprocessInput
from internal.evaluation.type import (
    EvalExpected,
    EvalPrediction,
    EvalSample,
    EvalSampleResult,
    EvalSummary,
    KeywordCounts,
    MetricCounts,
)
from internal.text_preprocessing.usecase.new import New as NewTextPreprocessingUseCase
from internal.text_preprocessing.type import Config as PreprocessorConfig
from internal.intent_classification.usecase.new import New as NewIntentClassificationUseCase
from internal.intent_classification.type import Config as IntentConfig
from internal.keyword_extraction.usecase.new import New as NewKeywordExtractionUseCase
from internal.keyword_extraction.type import Config as KeywordConfig
from internal.sentiment_analysis.usecase.new import New as NewSentimentAnalysisUseCase
from internal.sentiment_analysis.type import Config as SentimentConfig
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.phobert_onnx.type import PhoBERTConfig
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig
from pkg.logger.logger import Logger
from pkg.logger.type import LoggerConfig
from internal.model.constant import (
    LOGGER_COLORIZE,
    LOGGER_ENABLE_CONSOLE,
    LOGGER_ENABLE_TRACE_ID,
    LOGGER_SERVICE_NAME,
    PHOBERT_MAX_LENGTH,
    PHOBERT_MODEL_PATH,
    SPACY_CHUNK_WEIGHT,
    SPACY_ENTITY_WEIGHT,
    SPACY_MAX_KEYWORDS,
    SPACY_MODEL,
    SPACY_YAKE_DEDUP_LIM,
    SPACY_YAKE_LANGUAGE,
    SPACY_YAKE_MAX_KEYWORDS,
    SPACY_YAKE_N,
)


def load_eval_samples(path: str | Path) -> list[EvalSample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    samples: list[EvalSample] = []
    for item in raw:
        expected_raw = item.get("expected", {})
        samples.append(
            EvalSample(
                id=item["id"],
                text=item["text"],
                expected=EvalExpected(
                    intent=expected_raw.get("intent"),
                    sentiment=expected_raw.get("sentiment"),
                    keywords=list(expected_raw.get("keywords", [])),
                    aspects=list(expected_raw.get("aspects", [])),
                ),
            )
        )
    return samples


def build_eval_logger(level: str = "ERROR") -> Logger:
    return Logger(
        LoggerConfig(
            level=level,
            enable_console=LOGGER_ENABLE_CONSOLE,
            colorize=LOGGER_COLORIZE,
            service_name=LOGGER_SERVICE_NAME,
            enable_trace_id=LOGGER_ENABLE_TRACE_ID,
            json_output=False,
        )
    )


def load_eval_config() -> Config:
    os.environ.setdefault("ANALYTICS_MINIO_ENDPOINT", "eval-local")
    os.environ.setdefault("ANALYTICS_MINIO_ACCESS_KEY", "eval-local")
    os.environ.setdefault("ANALYTICS_MINIO_SECRET_KEY", "eval-local")
    return ConfigLoader().read_config()


def build_nlp_evaluator(config: Config, logger: Logger):
    repo_root = Path(__file__).resolve().parents[3]
    model_path = str(repo_root / PHOBERT_MODEL_PATH)

    preprocessor = NewTextPreprocessingUseCase(
        config=PreprocessorConfig(
            min_text_length=config.preprocessor.min_text_length,
            max_comments=config.preprocessor.max_comments,
        ),
        logger=logger,
    )
    intent_classifier = NewIntentClassificationUseCase(
        config=IntentConfig(
            patterns_path=config.intent_classifier.patterns_path,
            confidence_threshold=config.intent_classifier.confidence_threshold,
        ),
        logger=logger,
    )
    keyword_ai = SpacyYake(
        SpacyYakeConfig(
            spacy_model=SPACY_MODEL,
            yake_language=SPACY_YAKE_LANGUAGE,
            yake_n=SPACY_YAKE_N,
            yake_dedup_lim=SPACY_YAKE_DEDUP_LIM,
            yake_max_keywords=SPACY_YAKE_MAX_KEYWORDS,
            max_keywords=SPACY_MAX_KEYWORDS,
            entity_weight=SPACY_ENTITY_WEIGHT,
            chunk_weight=SPACY_CHUNK_WEIGHT,
        )
    )
    keyword_extractor = NewKeywordExtractionUseCase(
        config=KeywordConfig(
            aspect_dictionary_path=config.keyword_extraction.aspect_dictionary_path,
            enable_ai=config.keyword_extraction.enable_ai,
            ai_threshold=config.keyword_extraction.ai_threshold,
            max_keywords=config.keyword_extraction.max_keywords,
        ),
        ai_extractor=keyword_ai,
        logger=logger,
    )
    sentiment_model = PhoBERTONNX(
        PhoBERTConfig(
            model_path=model_path,
            max_length=PHOBERT_MAX_LENGTH,
        )
    )
    sentiment = NewSentimentAnalysisUseCase(
        config=SentimentConfig(
            context_window_size=config.sentiment_analysis.context_window_size,
            max_keywords_per_aspect=config.sentiment_analysis.max_keywords_per_aspect,
            threshold_positive=config.sentiment_analysis.threshold_positive,
            threshold_negative=config.sentiment_analysis.threshold_negative,
        ),
        phobert_model=sentiment_model,
        logger=logger,
    )
    return preprocessor, intent_classifier, keyword_extractor, sentiment


def predict_sample(sample: EvalSample, evaluators) -> EvalPrediction:
    preprocessor, intent_classifier, keyword_extractor, sentiment = evaluators

    preprocess_output = preprocessor.process(
        PreprocessInput(content=ContentInput(text=sample.text, transcription=""), comments=[])
    )
    clean_text = preprocess_output.clean_text
    intent_output = intent_classifier.process(IntentInput(text=clean_text))
    keyword_output = keyword_extractor.process(KeywordInput(text=clean_text))
    sentiment_output = sentiment.process(
        SentimentInput(
            text=clean_text,
            intent=intent_output.intent.name,
            keywords=[
                SAKeywordInput(
                    keyword=kw.keyword,
                    aspect=kw.aspect,
                    score=kw.score,
                    source=kw.source,
                )
                for kw in keyword_output.keywords
            ],
        )
    )

    aspects = sorted({kw.aspect for kw in keyword_output.keywords if kw.aspect})
    return EvalPrediction(
        intent=intent_output.intent.name,
        intent_confidence=intent_output.confidence,
        sentiment=sentiment_output.overall.label,
        sentiment_confidence=sentiment_output.overall.confidence,
        keywords=[kw.keyword for kw in keyword_output.keywords],
        aspects=aspects,
        clean_text=clean_text,
        is_spam=preprocess_output.is_spam,
        spam_reasons=list(preprocess_output.spam_reasons),
    )


def evaluate_samples(samples: Iterable[EvalSample], evaluators) -> tuple[list[EvalSampleResult], EvalSummary]:
    results: list[EvalSampleResult] = []
    intent_counts = MetricCounts()
    sentiment_counts = MetricCounts()
    keyword_counts = KeywordCounts()
    aspect_counts = KeywordCounts()

    for sample in samples:
        predicted = predict_sample(sample, evaluators)
        results.append(
            EvalSampleResult(
                sample_id=sample.id,
                expected=sample.expected,
                predicted=predicted,
            )
        )

        if sample.expected.intent is not None:
            intent_counts.total += 1
            if normalize_label(predicted.intent) == normalize_label(sample.expected.intent):
                intent_counts.correct += 1

        if sample.expected.sentiment is not None:
            sentiment_counts.total += 1
            if normalize_label(predicted.sentiment) == normalize_label(sample.expected.sentiment):
                sentiment_counts.correct += 1

        update_set_counts(keyword_counts, sample.expected.keywords, predicted.keywords)
        update_set_counts(aspect_counts, sample.expected.aspects, predicted.aspects)

    return results, EvalSummary(
        samples=len(results),
        intent=intent_counts,
        sentiment=sentiment_counts,
        keywords=keyword_counts,
        aspects=aspect_counts,
    )


def normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().upper()


def update_set_counts(counts: KeywordCounts, expected: list[str], predicted: list[str]) -> None:
    expected_set = {item.strip().lower() for item in expected if item and item.strip()}
    predicted_set = {item.strip().lower() for item in predicted if item and item.strip()}
    counts.true_positive += len(expected_set & predicted_set)
    counts.false_positive += len(predicted_set - expected_set)
    counts.false_negative += len(expected_set - predicted_set)


def ratio(correct: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(correct / total, 4)


def precision(counts: KeywordCounts) -> float | None:
    denom = counts.true_positive + counts.false_positive
    if denom == 0:
        return None
    return round(counts.true_positive / denom, 4)


def recall(counts: KeywordCounts) -> float | None:
    denom = counts.true_positive + counts.false_negative
    if denom == 0:
        return None
    return round(counts.true_positive / denom, 4)


def f1(counts: KeywordCounts) -> float | None:
    p = precision(counts)
    r = recall(counts)
    if p is None or r is None or p + r == 0:
        return None
    return round((2 * p * r) / (p + r), 4)


def summary_to_dict(summary: EvalSummary) -> dict[str, object]:
    return {
        "samples": summary.samples,
        "intent": {
            "correct": summary.intent.correct,
            "total": summary.intent.total,
            "accuracy": ratio(summary.intent.correct, summary.intent.total),
        },
        "sentiment": {
            "correct": summary.sentiment.correct,
            "total": summary.sentiment.total,
            "accuracy": ratio(summary.sentiment.correct, summary.sentiment.total),
        },
        "keywords": {
            "true_positive": summary.keywords.true_positive,
            "false_positive": summary.keywords.false_positive,
            "false_negative": summary.keywords.false_negative,
            "precision": precision(summary.keywords),
            "recall": recall(summary.keywords),
            "f1": f1(summary.keywords),
        },
        "aspects": {
            "true_positive": summary.aspects.true_positive,
            "false_positive": summary.aspects.false_positive,
            "false_negative": summary.aspects.false_negative,
            "precision": precision(summary.aspects),
            "recall": recall(summary.aspects),
            "f1": f1(summary.aspects),
        },
    }


__all__ = [
    "build_eval_logger",
    "build_nlp_evaluator",
    "evaluate_samples",
    "load_eval_samples",
    "precision",
    "predict_sample",
    "recall",
    "f1",
    "load_eval_config",
    "summary_to_dict",
    "update_set_counts",
]
