from internal.keyword_extraction.type import Aspect, Config, Input
from internal.keyword_extraction.usecase.process import process
from pkg.spacy_yake.type import SpacyYakeItem, SpacyYakeOutput


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warn(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


class _FakeAIExtractor:
    def extract(self, text):
        return SpacyYakeOutput(
            keywords=[
                SpacyYakeItem(
                    keyword="gọi hotline",
                    score=0.95,
                    rank=1,
                    type="chunk",
                    relevance=0.95,
                ),
                SpacyYakeItem(
                    keyword="đăng nhập",
                    score=0.9,
                    rank=2,
                    type="chunk",
                    relevance=0.9,
                ),
                SpacyYakeItem(
                    keyword="ahamova",
                    score=0.85,
                    rank=3,
                    type="chunk",
                    relevance=0.85,
                ),
            ],
            success=True,
        )


def test_dictionary_match_respects_word_boundaries():
    from internal.keyword_extraction.usecase.helpers import match_dictionary

    matches = match_dictionary("Ahamova xử lý đơn khá nhanh", {"đơ": Aspect.PERFORMANCE})

    assert matches == []


def test_process_filters_general_and_redundant_ai_keywords():
    output = process(
        input_data=Input(text="App Ahamova lỗi đăng nhập, gọi hotline để hỗ trợ."),
        config=Config(enable_ai=True, ai_threshold=5, max_keywords=10),
        aspect_dict={},
        keyword_map={
            "hotline": Aspect.SERVICE,
            "app": Aspect.PERFORMANCE,
            "lỗi đăng nhập": Aspect.PERFORMANCE,
        },
        ai_extractor=_FakeAIExtractor(),
        logger=_NoopLogger(),
    )

    assert [kw.keyword for kw in output.keywords] == ["hotline", "app", "lỗi đăng nhập", "đăng nhập"]
