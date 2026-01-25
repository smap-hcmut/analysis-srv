"""Performance and benchmark tests for PhoBERT."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # type: ignore
import time

from infrastructure.ai.phobert_onnx import PhoBERTONNX


@pytest.mark.skipif(
    not Path("infrastructure/phobert/models/model_quantized.onnx").exists(),
    reason="Model not downloaded",
)
@pytest.mark.benchmark
class TestPerformance:
    """Performance and benchmark tests."""

    @pytest.fixture(scope="class")
    def phobert(self):
        """Load PhoBERT model once."""
        return PhoBERTONNX()

    def test_single_inference_speed(self, phobert):
        """Test single inference completes within 100ms."""
        text = "Xe VinFast VF8 có thiết kế đẹp, pin trâu nhưng giá hơi cao"

        start = time.time()
        result = phobert.predict(text)
        duration = (time.time() - start) * 1000  # Convert to ms

        assert duration < 100, f"Inference took {duration:.2f}ms, expected < 100ms"
        assert result["rating"] in range(1, 6)

    def test_batch_inference_speed(self, phobert):
        """Test batch inference performance."""
        texts = ["Sản phẩm tốt", "Sản phẩm tệ", "Sản phẩm bình thường"] * 10  # 30 texts total

        start = time.time()
        results = phobert.predict_batch(texts)
        duration = time.time() - start

        avg_time = (duration / len(texts)) * 1000

        assert len(results) == 30
        assert avg_time < 200, f"Average time {avg_time:.2f}ms, expected < 200ms"

    def test_model_loading_time(self):
        """Test model loading time."""
        start = time.time()
        phobert = PhoBERTONNX()
        duration = time.time() - start

        assert duration < 5.0, f"Model loading took {duration:.2f}s, expected < 5s"

    @pytest.mark.skip(reason="Requires psutil package")
    def test_memory_usage(self, phobert):
        """Test memory usage is reasonable."""
        import psutil  # type: ignore
        import os

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # Run multiple predictions
        for _ in range(100):
            phobert.predict("Test text")

        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        # Memory increase should be minimal (< 100MB)
        assert mem_increase < 100, f"Memory increased by {mem_increase:.2f}MB"

    def test_throughput(self, phobert):
        """Test throughput (predictions per second)."""
        texts = ["Sản phẩm tốt"] * 100

        start = time.time()
        for text in texts:
            phobert.predict(text)
        duration = time.time() - start

        throughput = len(texts) / duration

        # Should process at least 5 predictions per second
        assert throughput >= 5, f"Throughput: {throughput:.2f} pred/s, expected >= 5"

    def test_cold_start_vs_warm(self, phobert):
        """Test cold start vs warm inference time."""
        text = "Sản phẩm chất lượng cao"

        # Cold start (first prediction)
        start = time.time()
        phobert.predict(text)
        cold_time = (time.time() - start) * 1000

        # Warm predictions
        warm_times = []
        for _ in range(10):
            start = time.time()
            phobert.predict(text)
            warm_times.append((time.time() - start) * 1000)

        avg_warm_time = sum(warm_times) / len(warm_times)

        # Warm predictions should be reasonably close to or faster than cold start.
        # Allow a looser bound to avoid flakiness on different machines.
        assert (
            avg_warm_time <= cold_time * 2.0
        ), f"Warm time {avg_warm_time:.2f}ms should be <= 2x cold time {cold_time:.2f}ms"
