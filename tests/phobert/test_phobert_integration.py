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
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_class_structure():
    """Test that the class has the expected structure."""
    print("\nTesting class structure...")
    try:
        from infrastructure.ai import PhoBERTONNX

        # Check class attributes
        assert hasattr(PhoBERTONNX, "SENTIMENT_MAP"), "Missing SENTIMENT_MAP"
        assert hasattr(PhoBERTONNX, "SENTIMENT_LABELS"), "Missing SENTIMENT_LABELS"
        assert len(PhoBERTONNX.SENTIMENT_MAP) == 5, "SENTIMENT_MAP should have 5 entries"
        assert len(PhoBERTONNX.SENTIMENT_LABELS) == 5, "SENTIMENT_LABELS should have 5 entries"

        # Check methods
        assert hasattr(PhoBERTONNX, "predict"), "Missing predict method"
        assert hasattr(PhoBERTONNX, "predict_batch"), "Missing predict_batch method"

        print("✅ Class structure is correct")
        return True
    except AssertionError as e:
        print(f"❌ Structure test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_initialization_without_model():
    """Test that initialization fails gracefully without model."""
    print("\nTesting initialization without model...")
    try:
        from infrastructure.ai import PhoBERTONNX

        try:
            model = PhoBERTONNX(model_path="/nonexistent/path")
            print("❌ Should have raised FileNotFoundError")
            return False
        except FileNotFoundError as e:
            if "Model directory not found" in str(e):
                print("✅ Correctly raises FileNotFoundError with proper message")
                return True
            else:
                print(f"❌ Wrong error message: {e}")
                return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


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
