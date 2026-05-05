from internal.sentiment_analysis.type import (
    Config,
    Input,
    KeywordInput,
)
from internal.sentiment_analysis.usecase.process import process_batch
from pkg.phobert_onnx.type import PhobertOnnxOutput, PhobertOnnxProbability


class _FakePhoBERT:
    def __init__(self):
        self.calls = []

    def predict_batch(self, texts, return_probabilities=True):
        self.calls.append((list(texts), return_probabilities))
        probs = None
        if return_probabilities:
            probs = PhobertOnnxProbability(NEGATIVE=0.1, POSITIVE=0.8, NEUTRAL=0.1)
        return [
            PhobertOnnxOutput(
                rating=1,
                sentiment="Tich cuc",
                confidence=0.8,
                probabilities=probs,
                label="Tich cuc",
            )
            for _ in texts
        ]


def test_process_batch_caps_keyword_contexts_per_aspect(monkeypatch):
    import internal.sentiment_analysis.usecase.process as process_module

    monkeypatch.setattr(
        process_module,
        "extract_smart_window",
        lambda text, keyword, context_window_size, position=None: f"context:{keyword}",
    )

    model = _FakePhoBERT()
    outputs = process_batch(
        input_list=[
            Input(
                text="vinfast service",
                keywords=[
                    KeywordInput(keyword="bao hanh", aspect="SERVICE", score=1.0),
                    KeywordInput(keyword="showroom", aspect="SERVICE", score=0.9),
                    KeywordInput(keyword="phu tung", aspect="SERVICE", score=0.8),
                    KeywordInput(keyword="nhan vien", aspect="SERVICE", score=0.7),
                ],
            )
        ],
        phobert_model=model,
        config=Config(max_keywords_per_aspect=2),
    )

    assert len(model.calls) == 2
    assert model.calls[0][0] == ["vinfast service"]
    assert model.calls[1][0] == ["context:bao hanh", "context:showroom"]

    service = outputs[0].aspects["SERVICE"]
    assert service.mentions == 4
    assert service.keywords == ["bao hanh", "showroom", "phu tung", "nhan vien"]
