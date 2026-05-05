from internal.sentiment_analysis.type import Config, Input, SentimentResult
from internal.sentiment_analysis.usecase.process import process, process_batch


class _UnusedModel:
    pass


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warn(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def test_process_neutralizes_support_intent(monkeypatch):
    import internal.sentiment_analysis.usecase.process as process_module

    monkeypatch.setattr(
        process_module,
        "analyze_overall",
        lambda text, phobert_model, config, logger: SentimentResult(
            label="POSITIVE",
            score=0.5,
            confidence=0.6,
            probabilities={},
            rating=4,
        ),
    )

    output = process(
        input_data=Input(text="Cho mình hỏi đăng ký tài khoản như thế nào?", intent="SUPPORT"),
        phobert_model=_UnusedModel(),
        config=Config(),
        logger=_NoopLogger(),
    )

    assert output.overall.label == "NEUTRAL"
    assert output.overall.score == 0.0


def test_process_batch_negativizes_complaint_intent(monkeypatch):
    import internal.sentiment_analysis.usecase.process as process_module

    monkeypatch.setattr(
        process_module,
        "analyze_overall_batch",
        lambda texts, phobert_model, config, logger: [
            SentimentResult(
                label="POSITIVE",
                score=0.5,
                confidence=0.6,
                probabilities={},
                rating=4,
            )
            for _ in texts
        ],
    )

    outputs = process_batch(
        input_list=[Input(text="Hotline không ai trả lời cả ngày.", intent="COMPLAINT")],
        phobert_model=_UnusedModel(),
        config=Config(),
        logger=_NoopLogger(),
    )

    assert outputs[0].overall.label == "NEGATIVE"
    assert outputs[0].overall.score == -0.5
