"""Performance tests for SpaCy-YAKE keyword extraction."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # type: ignore
import time
from infrastructure.ai.spacyyake_extractor import SpacyYakeExtractor

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # type: ignore


def check_spacy_model_available():
    """Check if SpaCy model is available."""
    try:
        import spacy  # type: ignore

        try:
            spacy.load("en_core_web_sm")
            return True
        except OSError:
            return False
    except ImportError:
        return False


def check_yake_available():
    """Check if YAKE is available."""
    try:
        import yake  # type: ignore

        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not (check_spacy_model_available() and check_yake_available()),
    reason="SpaCy model or YAKE not available. Run 'make download-spacy-model' first.",
)
class TestPerformance:
    """Performance benchmark tests for SpaCy-YAKE."""

    @pytest.fixture(scope="class")
    def extractor(self):
        """Create extractor instance once for all tests."""
        return SpacyYakeExtractor()

    @pytest.fixture
    def sample_text(self):
        """Sample text for testing."""
        return """
        Machine learning and artificial intelligence are transforming the technology industry.
        Python is a popular programming language for data science and web development.
        Cloud computing enables scalable infrastructure for modern applications.
        """

    def test_single_extraction_speed(self, extractor, sample_text):
        """Test single text extraction speed (<500ms target)."""
        start = time.time()
        result = extractor.extract(sample_text)
        duration = (time.time() - start) * 1000

        assert result.success
        assert duration < 500, f"Extraction took {duration:.2f}ms, expected <500ms"
        print(f"\n✓ Single extraction: {duration:.2f}ms")

    def test_batch_extraction_speed(self, extractor):
        """Test batch extraction speed."""
        texts = [
            "Machine learning is transforming data science.",
            "Python is a popular programming language.",
            "Cloud computing enables scalable infrastructure.",
        ] * 10  # 30 texts total

        start = time.time()
        results = extractor.extract_batch(texts)
        duration = time.time() - start
        avg_time = (duration / len(texts)) * 1000

        assert len(results) == 30
        assert all(r.success for r in results)
        assert avg_time < 300, f"Average time {avg_time:.2f}ms, expected <300ms"
        print(f"\n✓ Batch extraction (30 texts): {avg_time:.2f}ms per text")

    def test_model_loading_time(self):
        """Test model loading time."""
        start = time.time()
        extractor = SpacyYakeExtractor()
        duration = time.time() - start

        assert duration < 10.0, f"Model loading took {duration:.2f}s, expected <10s"
        print(f"\n✓ Model loading: {duration:.2f}s")

    @pytest.mark.skip(reason="Requires psutil package")
    def test_memory_usage(self, extractor, sample_text):
        """Test memory usage is reasonable."""
        process = psutil.Process()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # Extract 100 times
        for _ in range(100):
            extractor.extract(sample_text)

        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        assert mem_increase < 100, f"Memory increased by {mem_increase:.2f}MB, expected <100MB"
        print(f"\n✓ Memory increase (100 extractions): {mem_increase:.2f}MB")

    def test_throughput(self, extractor):
        """Test throughput (predictions per second)."""
        texts = [
            "Great product with excellent quality!",
            "Poor service and bad experience.",
            "Average performance, nothing special.",
        ] * 20  # 60 texts

        start = time.time()
        results = extractor.extract_batch(texts)
        duration = time.time() - start
        throughput = len(texts) / duration

        assert all(r.success for r in results)
        assert throughput >= 5, f"Throughput {throughput:.2f} pred/s, expected ≥5"
        print(f"\n✓ Throughput: {throughput:.2f} predictions/second")

    def test_cold_start_vs_warm(self, sample_text):
        """Test cold start vs warm performance."""
        # Cold start (first extraction)
        extractor = SpacyYakeExtractor()
        start = time.time()
        result1 = extractor.extract(sample_text)
        cold_duration = (time.time() - start) * 1000

        # Warm (subsequent extractions)
        start = time.time()
        result2 = extractor.extract(sample_text)
        warm_duration = (time.time() - start) * 1000

        assert result1.success and result2.success
        # Warm should be faster or similar
        print(f"\n✓ Cold start: {cold_duration:.2f}ms, Warm: {warm_duration:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
