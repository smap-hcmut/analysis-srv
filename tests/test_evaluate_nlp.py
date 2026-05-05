from internal.evaluation.type import (
    EvalExpected,
    EvalPrediction,
    EvalSample,
    EvalSummary,
    KeywordCounts,
    MetricCounts,
)
from internal.evaluation.usecase.evaluate_nlp import (
    evaluate_samples,
    f1,
    precision,
    recall,
    summary_to_dict,
)


def test_keyword_metrics_are_calculated_as_expected():
    counts = KeywordCounts(true_positive=2, false_positive=1, false_negative=1)

    assert precision(counts) == 0.6667
    assert recall(counts) == 0.6667
    assert f1(counts) == 0.6667


def test_summary_to_dict_reports_accuracy_and_set_metrics():
    summary = EvalSummary(
        samples=2,
        intent=MetricCounts(correct=1, total=2),
        sentiment=MetricCounts(correct=2, total=2),
        keywords=KeywordCounts(true_positive=3, false_positive=1, false_negative=2),
        aspects=KeywordCounts(true_positive=2, false_positive=0, false_negative=1),
    )

    result = summary_to_dict(summary)

    assert result["intent"]["accuracy"] == 0.5
    assert result["sentiment"]["accuracy"] == 1.0
    assert result["keywords"]["precision"] == 0.75
    assert result["keywords"]["recall"] == 0.6
    assert result["aspects"]["f1"] == 0.8


def test_evaluate_samples_scores_predictions_from_injected_predictor(monkeypatch):
    import internal.evaluation.usecase.evaluate_nlp as eval_module

    predictions = {
        "s1": EvalPrediction(
            intent="COMPLAINT",
            sentiment="NEGATIVE",
            keywords=["bảo hành", "hỗ trợ"],
            aspects=["SERVICE"],
        ),
        "s2": EvalPrediction(
            intent="DISCUSSION",
            sentiment="NEGATIVE",
            keywords=["thiết kế"],
            aspects=["DESIGN"],
        ),
    }

    monkeypatch.setattr(
        eval_module,
        "predict_sample",
        lambda sample, evaluators: predictions[sample.id],
    )

    samples = [
        EvalSample(
            id="s1",
            text="a",
            expected=EvalExpected(
                intent="COMPLAINT",
                sentiment="NEGATIVE",
                keywords=["bảo hành", "hỗ trợ", "nhân viên"],
                aspects=["SERVICE"],
            ),
        ),
        EvalSample(
            id="s2",
            text="b",
            expected=EvalExpected(
                intent="DISCUSSION",
                sentiment="POSITIVE",
                keywords=["thiết kế"],
                aspects=["DESIGN"],
            ),
        ),
    ]

    _, summary = evaluate_samples(samples, evaluators=None)

    assert summary.samples == 2
    assert summary.intent.correct == 2
    assert summary.intent.total == 2
    assert summary.sentiment.correct == 1
    assert summary.sentiment.total == 2
    assert summary.keywords.true_positive == 3
    assert summary.keywords.false_positive == 0
    assert summary.keywords.false_negative == 1
