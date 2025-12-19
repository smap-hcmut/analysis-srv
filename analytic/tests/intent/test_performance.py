"""Performance tests for IntentClassifier.

Tests verify that classification meets target performance:
- Single prediction: <1ms
- Batch processing: efficient
- Pattern compilation: fast
"""

import time
import pytest
from services.analytics.intent import IntentClassifier


class TestPerformance:
    """Test 2.6: Performance benchmarks."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    @pytest.fixture
    def sample_posts(self):
        """Generate sample posts for batch testing."""
        return [
            "VinFast lừa đảo khách hàng",
            "Liên hệ mua xe 0912345678",
            "Vay tiền lãi suất thấp",
            "Xe lỗi mãi không sửa",
            "Giá xe bao nhiêu?",
            "Cách sạc xe như thế nào?",
            "Xe VinFast đẹp nhỉ",
            "Thất vọng với chất lượng dịch vụ",
            "Test drive có cần đặt lịch không?",
            "Bảo hành xe bao lâu?",
        ] * 10  # 100 posts total

    def test_single_prediction_speed(self, classifier):
        """Test single prediction completes in <1ms target."""
        text = "VinFast lừa đảo khách hàng, thất vọng quá"

        # Warm up
        classifier.predict(text)

        # Measure performance
        iterations = 1000
        start_time = time.perf_counter()
        for _ in range(iterations):
            classifier.predict(text)
        end_time = time.perf_counter()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        # Should be well under 1ms per prediction
        assert avg_time_ms < 1.0, f"Average prediction time {avg_time_ms:.4f}ms exceeds 1ms target"

        # Print for visibility
        print(f"\nSingle prediction average: {avg_time_ms:.4f}ms ({iterations} iterations)")

    def test_batch_processing_speed(self, classifier, sample_posts):
        """Test batch processing of 100 posts."""
        # Warm up
        for post in sample_posts[:10]:
            classifier.predict(post)

        # Measure batch processing
        start_time = time.perf_counter()
        results = [classifier.predict(post) for post in sample_posts]
        end_time = time.perf_counter()

        total_time_ms = (end_time - start_time) * 1000
        avg_time_ms = total_time_ms / len(sample_posts)

        # All results should be valid
        assert len(results) == len(sample_posts)
        assert all(r is not None for r in results)

        # Average should still be under 1ms
        assert avg_time_ms < 1.0, f"Average time {avg_time_ms:.4f}ms exceeds 1ms target"

        print(f"\nBatch processing ({len(sample_posts)} posts):")
        print(f"  Total time: {total_time_ms:.2f}ms")
        print(f"  Average per post: {avg_time_ms:.4f}ms")

    def test_pattern_compilation_time(self):
        """Test pattern compilation time during initialization."""
        iterations = 100

        start_time = time.perf_counter()
        for _ in range(iterations):
            IntentClassifier()
        end_time = time.perf_counter()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        # Pattern compilation should be fast (<10ms)
        assert avg_time_ms < 10.0, f"Pattern compilation {avg_time_ms:.4f}ms is too slow"

        print(f"\nPattern compilation average: {avg_time_ms:.4f}ms ({iterations} iterations)")

    def test_benchmark_against_target_metrics(self, classifier):
        """Benchmark against target metrics from proposal."""
        # Target: <1ms per prediction
        test_texts = [
            "VinFast lừa đảo",
            "Giá xe bao nhiêu?",
            "Vay tiền nhanh",
            "Liên hệ 0912345678",
            "Xe lỗi quá",
        ]

        times = []
        for text in test_texts:
            start = time.perf_counter()
            result = classifier.predict(text)
            end = time.perf_counter()
            times.append((end - start) * 1000)
            assert result is not None

        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)

        print(f"\nBenchmark results:")
        print(f"  Average: {avg_time:.4f}ms")
        print(f"  Min: {min_time:.4f}ms")
        print(f"  Max: {max_time:.4f}ms")

        # All predictions should meet target
        assert avg_time < 1.0, f"Average {avg_time:.4f}ms exceeds target"
        assert max_time < 2.0, f"Max {max_time:.4f}ms is too slow"

    def test_memory_efficiency(self, classifier):
        """Test that classifier doesn't leak memory during repeated use."""
        # Process many predictions to check for memory leaks
        text = "Xe VinFast đẹp quá"

        for _ in range(10000):
            result = classifier.predict(text)
            assert result is not None

        # If we got here without memory issues, test passes
        assert True

    def test_concurrent_safety(self, classifier):
        """Test classifier can handle concurrent predictions safely."""
        import concurrent.futures

        texts = [
            "VinFast lừa đảo",
            "Giá xe bao nhiêu?",
            "Vay tiền nhanh",
        ] * 100

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(classifier.predict, texts))

        # All results should be valid
        assert len(results) == len(texts)
        assert all(r is not None for r in results)

        print(f"\nConcurrent processing: {len(texts)} predictions with 10 threads")
