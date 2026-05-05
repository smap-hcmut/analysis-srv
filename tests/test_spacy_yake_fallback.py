import subprocess
from types import SimpleNamespace

from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig


class _FakeKeywordExtractor:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def extract_keywords(self, text: str):
        return [("vinfast", 0.05), ("service", 0.25)]


def test_spacy_probe_failure_falls_back_to_yake_only(monkeypatch):
    import pkg.spacy_yake.spacy_yake as spacy_yake_module

    monkeypatch.setattr(
        spacy_yake_module,
        "yake",
        SimpleNamespace(KeywordExtractor=_FakeKeywordExtractor),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=-7,
            stdout="",
            stderr="Bus error: 10",
        ),
    )

    extractor = SpacyYake(
        SpacyYakeConfig(max_keywords=5, entity_weight=1.0, chunk_weight=1.0)
    )

    result = extractor.extract("VinFast service rat te")

    assert result.success is True
    assert result.method_name == "yake_fallback"
    assert result.metadata["method"] == "yake_fallback"
    assert result.metadata["spacy_available"] is False
    assert result.metadata["spacy_mode"] == "disabled"
    assert result.metadata["entities_count"] == 0
    assert result.metadata["noun_chunks_count"] == 0
    assert result.metadata["yake_keywords_count"] == 2
    assert [item.keyword for item in result.keywords] == ["vinfast", "service"]
