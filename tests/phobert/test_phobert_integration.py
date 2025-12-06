#!/usr/bin/env python3
"""
Simple test runner for PhoBERT integration.
This bypasses pytest import issues by running tests directly.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from infrastructure.ai import PhoBERTONNX

        print("✅ PhoBERTONNX imported successfully")
        assert True  # Use assert instead of return for pytest
    except Exception as e:
        print(f"❌ Import failed: {e}")
        assert False, f"Import failed: {e}"


def test_class_structure():
    """Test that the class has the expected structure."""
    print("\nTesting class structure...")
    from infrastructure.ai import PhoBERTONNX
    from infrastructure.ai.constants import SENTIMENT_MAP, SENTIMENT_LABELS

    # Check constants are available
    assert len(SENTIMENT_MAP) == 3, "SENTIMENT_MAP should have 3 entries (3-class model)"
    assert len(SENTIMENT_LABELS) == 5, "SENTIMENT_LABELS should have 5 entries"

    # Check methods
    assert hasattr(PhoBERTONNX, "predict"), "Missing predict method"
    assert hasattr(PhoBERTONNX, "predict_batch"), "Missing predict_batch method"
    assert hasattr(PhoBERTONNX, "_segment_text"), "Missing _segment_text method"
    assert hasattr(PhoBERTONNX, "_postprocess"), "Missing _postprocess method"

    print("✅ Class structure is correct")


def test_initialization_without_model():
    """Test that initialization fails gracefully without model."""
    print("\nTesting initialization without model...")
    import pytest
    from infrastructure.ai import PhoBERTONNX

    with pytest.raises(FileNotFoundError) as exc_info:
        model = PhoBERTONNX(model_path="/nonexistent/path")

    assert "Model directory not found" in str(exc_info.value)
    print("✅ Correctly raises FileNotFoundError with proper message")


def main():
    """Run all tests."""
    print("=" * 60)
    print("PhoBERT Integration Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_class_structure,
        test_initialization_without_model,
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All tests passed!")
        print("\nNote: Full integration tests require the model to be downloaded.")
        print("Run 'make download-phobert' to download the model.")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
