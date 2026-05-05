import numpy as np

from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX


class _FakeTokenizer:
    def __init__(self):
        self.calls = []

    def __call__(self, texts, **kwargs):
        self.calls.append(list(texts))
        batch = len(texts)
        return {
            "input_ids": np.ones((batch, 4), dtype=np.int64),
            "attention_mask": np.ones((batch, 4), dtype=np.int64),
        }


class _FakeModel:
    def __init__(self):
        self.calls = []

    def run(self, _, inputs):
        self.calls.append(inputs)
        batch = inputs["input_ids"].shape[0]
        logits = np.array(
            [[0.1, 2.0, 0.2] for _ in range(batch)],
            dtype=np.float32,
        )
        return [logits]


def test_predict_batch_deduplicates_repeated_texts():
    model = PhoBERTONNX.__new__(PhoBERTONNX)
    model.config = type("Config", (), {"max_length": 256})()
    model.tokenizer = _FakeTokenizer()
    model.model = _FakeModel()
    model._segment_text = lambda text: f"seg::{text}"

    outputs = model.predict_batch(
        ["xe dep", "xe dep", "dich vu te", "dich vu te", "xe dep"],
        return_probabilities=False,
    )

    assert len(model.tokenizer.calls) == 1
    assert model.tokenizer.calls[0] == ["seg::xe dep", "seg::dich vu te"]
    assert len(model.model.calls) == 1
    assert model.model.calls[0]["input_ids"].shape[0] == 2
    assert len(outputs) == 5
    assert outputs[0].label == outputs[1].label == outputs[4].label
    assert outputs[2].label == outputs[3].label
