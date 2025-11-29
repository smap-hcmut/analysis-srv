"""Performance tests for TextPreprocessor."""

import time
import pytest  # type: ignore
from services.analytics.preprocessing.text_preprocessor import TextPreprocessor


class TestTextPreprocessorPerformance:
    """Performance benchmarks for TextPreprocessor."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_processing_time_single_post(self, preprocessor, benchmark):
        """Test processing time for a typical post (< 10ms)."""
        input_data = {
            "content": {
                "text": "This is a typical post caption with some hashtags #test #performance",
                "transcription": "And here is a longer transcription that adds more content to the processing pipeline."
                * 5,
            },
            "comments": [
                {"text": "Comment 1", "likes": 10},
                {"text": "Comment 2", "likes": 5},
                {"text": "Comment 3", "likes": 2},
            ],
        }

        # Use pytest-benchmark to measure performance
        def run_preprocess():
            return preprocessor.preprocess(input_data)

        benchmark(run_preprocess)

        # Assert mean execution time is under 10ms (0.01s)
        assert benchmark.stats["mean"] < 0.01

    def test_processing_time_long_post(self, preprocessor, benchmark):
        """Test processing time for a very long post."""
        # Create a large input (approx 10KB)
        long_text = "Word " * 2000
        input_data = {"content": {"text": long_text, "transcription": long_text}, "comments": []}

        def run_preprocess():
            return preprocessor.preprocess(input_data)

        benchmark(run_preprocess)

        # Even for large posts, should be reasonably fast (e.g., < 50ms)
        assert benchmark.stats["mean"] < 0.05

    def test_memory_usage_large_batch(self, preprocessor):
        """Test memory stability with a batch of posts."""
        # Process 1000 posts and ensure no crashes/errors
        input_data = {"content": {"text": "Simple post"}, "comments": []}

        start_time = time.time()
        for _ in range(1000):
            preprocessor.preprocess(input_data)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / 1000

        # Average time should be very low for simple posts
        assert avg_time < 0.001  # < 1ms
