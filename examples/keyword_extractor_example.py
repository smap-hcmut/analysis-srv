"""Example usage of KeywordExtractor for hybrid keyword extraction.

This example demonstrates:
1. Dictionary matching with automotive terms
2. AI discovery for new keywords (when SpaCy available)
3. Aspect mapping for all keywords
4. Hybrid logic combining both sources
5. Performance benchmarking

Requirements:
    - Vietnamese SpaCy model for AI discovery (optional):
      python -m spacy download vi_core_news_lg
    - The example works in dictionary-only mode if SpaCy model unavailable

Usage:
    python examples/keyword_extractor_example.py

Note:
    - Dictionary matching works without SpaCy (80% functionality)
    - AI discovery requires Vietnamese model (full 100% functionality)
    - Fallback to dictionary-only mode is automatic
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.analytics.keyword import Aspect, KeywordExtractor


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 80}")
    print(f" {title}")
    print("=" * 80)


def print_result(result, show_metadata=True):
    """Pretty print extraction result."""
    if not result.keywords:
        print("  No keywords extracted")
        return

    print(f"  Found {len(result.keywords)} keywords:")
    for i, kw in enumerate(result.keywords, 1):
        print(
            f"    {i}. '{kw['keyword']}' → {kw['aspect']} "
            f"(score={kw['score']:.2f}, source={kw['source']})"
        )

    if show_metadata:
        print(f"\n  Metadata:")
        print(f"    - Dictionary matches: {result.metadata['dict_matches']}")
        print(f"    - AI matches: {result.metadata['ai_matches']}")
        print(f"    - Total keywords: {result.metadata['total_keywords']}")
        print(f"    - Extraction time: {result.metadata['total_time_ms']:.2f}ms")


def example_1_dictionary_matching():
    """Example 1: Dictionary matching with automotive terms."""
    print_section("Example 1: Dictionary Matching")

    extractor = KeywordExtractor()
    extractor.enable_ai = False  # Dictionary only

    # Example 1a: Simple automotive review
    print("\nExample 1a: Simple automotive review")
    text = "Xe đẹp nhưng pin yếu quá, giá hơi đắt"
    print(f"Text: {text}")

    result = extractor.extract(text)
    print_result(result)

    # Example 1b: Mixed aspects
    print("\nExample 1b: Multiple aspects")
    text = """
    Thiết kế ngoại thất đẹp, nội thất sang trọng.
    Pin tốt, sạc nhanh, động cơ khỏe.
    Giá cả hợp lý, chi phí lăn bánh ok.
    Bảo hành tốt, nhân viên nhiệt tình.
    """
    print(f"Text: {text[:100]}...")

    result = extractor.extract(text)
    print_result(result)

    # Show aspect distribution
    aspect_counts = {}
    for kw in result.keywords:
        aspect = kw["aspect"]
        aspect_counts[aspect] = aspect_counts.get(aspect, 0) + 1

    print("\n  Aspect distribution:")
    for aspect, count in sorted(aspect_counts.items()):
        print(f"    - {aspect}: {count} keywords")


def example_2_aspect_mapping():
    """Example 2: Aspect mapping for all keywords."""
    print_section("Example 2: Aspect Mapping")

    extractor = KeywordExtractor()
    extractor.enable_ai = False

    # Show examples for each aspect
    aspect_examples = {
        Aspect.DESIGN: "Thiết kế đẹp, màu xe sang, ngoại thất bóng bẩy",
        Aspect.PERFORMANCE: "Pin mạnh, sạc nhanh, động cơ khỏe, vận hành êm",
        Aspect.PRICE: "Giá rẻ, chi phí thấp, lăn bánh hợp lý, trả góp dễ",
        Aspect.SERVICE: "Bảo hành tốt, nhân viên nhiệt tình, showroom chuyên nghiệp",
    }

    for aspect, text in aspect_examples.items():
        print(f"\n{aspect.value} aspect:")
        print(f"  Text: {text}")

        result = extractor.extract(text)

        # Filter to show only this aspect
        aspect_keywords = [kw for kw in result.keywords if kw["aspect"] == aspect.value]
        print(f"  Keywords ({len(aspect_keywords)}):")
        for kw in aspect_keywords:
            print(f"    - {kw['keyword']}")


def example_3_hybrid_logic():
    """Example 3: Hybrid logic combining dictionary + AI."""
    print_section("Example 3: Hybrid Logic (Dictionary + AI)")

    extractor = KeywordExtractor()
    extractor.enable_ai = True  # Enable AI discovery
    extractor.ai_threshold = 3  # Run AI if dict matches < 3

    # Example with few dictionary matches (triggers AI)
    print("\nExample 3a: Text with new terms (AI discovery)")
    text = "VinFast ra mẫu xe mới"
    print(f"Text: {text}")

    try:
        result = extractor.extract(text)
        print_result(result)

        # Show which sources were used
        sources = {kw["source"] for kw in result.keywords}
        print(f"\n  Sources used: {', '.join(sources)}")

    except (OSError, SystemExit):
        print("  Note: SpaCy model not available, AI discovery disabled")
        extractor.enable_ai = False
        result = extractor.extract(text)
        print_result(result)

    # Example with many dictionary matches (skips AI)
    print("\nExample 3b: Text with many dictionary terms (skips AI)")
    text = "Pin tốt, sạc nhanh, động cơ khỏe, giá rẻ, xe đẹp"
    print(f"Text: {text}")

    result = extractor.extract(text)
    print_result(result)

    print(f"\n  AI was {'NOT ' if result.metadata['ai_matches'] == 0 else ''}triggered")
    print(
        f"  (threshold: {extractor.ai_threshold}, dict matches: {result.metadata['dict_matches']})"
    )


def example_4_real_world_reviews():
    """Example 4: Real-world Vietnamese automotive reviews."""
    print_section("Example 4: Real-World Reviews")

    extractor = KeywordExtractor()
    extractor.enable_ai = False  # Dictionary only for speed

    reviews = [
        {
            "title": "Positive review",
            "text": """
            Mình vừa mới nhận xe VinFast VF8 được 2 tuần.
            Thiết kế ngoại thất rất đẹp và sang trọng, nội thất cũng ok.
            Pin thì tạm ổn, sạc đầy mất khoảng 8 tiếng ở nhà.
            Giá hơi đắt so với phân khúc nhưng chấp nhận được.
            Bảo hành 10 năm, nhân viên showroom tư vấn nhiệt tình.
            """,
        },
        {
            "title": "Negative review",
            "text": """
            Pin yếu quá, chạy được có 200km là hết.
            Sạc chậm, mất cả ngày mới đầy.
            Giá đắt mà chất lượng không xứng.
            Bảo hành kém, nhân viên thái độ tệ.
            """,
        },
        {
            "title": "Mixed review",
            "text": """
            Xe đẹp, thiết kế hiện đại, nội thất sang.
            Nhưng pin yếu, sạc lâu, giá đắt.
            Bảo hành ok, showroom tốt.
            """,
        },
    ]

    for review in reviews:
        print(f"\n{review['title']}:")
        print(f"  Text: {review['text'][:80]}...")

        result = extractor.extract(review["text"])

        # Group by aspect
        by_aspect = {}
        for kw in result.keywords:
            aspect = kw["aspect"]
            if aspect not in by_aspect:
                by_aspect[aspect] = []
            by_aspect[aspect].append(kw["keyword"])

        print(f"  Keywords by aspect:")
        for aspect in sorted(by_aspect.keys()):
            keywords_str = ", ".join(by_aspect[aspect][:5])  # Show first 5
            more = len(by_aspect[aspect]) - 5
            if more > 0:
                keywords_str += f" (+{more} more)"
            print(f"    - {aspect}: {keywords_str}")


def example_5_performance_benchmark():
    """Example 5: Performance benchmarking."""
    print_section("Example 5: Performance Benchmarking")

    extractor = KeywordExtractor()
    extractor.enable_ai = False  # Dictionary only for consistent timing

    # Test 1: Single extraction
    print("\nTest 1: Single extraction")
    text = "Pin tốt, sạc nhanh, động cơ khỏe, giá rẻ, xe đẹp, bảo hành tốt"

    result = extractor.extract(text)
    print(f"  Text: {text}")
    print(f"  Extraction time: {result.metadata['total_time_ms']:.2f}ms")
    print(f"  Keywords extracted: {len(result.keywords)}")

    # Test 2: Batch processing
    print("\nTest 2: Batch processing (100 posts)")
    posts = [text] * 100

    start_time = time.perf_counter()
    results = [extractor.extract(post) for post in posts]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    avg_time_ms = elapsed_ms / len(posts)
    print(f"  Total posts: {len(posts)}")
    print(f"  Total time: {elapsed_ms:.2f}ms")
    print(f"  Average per post: {avg_time_ms:.2f}ms")
    print(f"  Throughput: {1000 / avg_time_ms:.0f} posts/second")

    # Test 3: Dictionary statistics
    print("\nTest 3: Dictionary statistics")
    print(f"  Aspects loaded: {len(extractor.aspect_dict)}")
    print(f"  Total keyword mappings: {len(extractor.keyword_map)}")

    for aspect in [Aspect.DESIGN, Aspect.PERFORMANCE, Aspect.PRICE, Aspect.SERVICE]:
        count = sum(1 for a in extractor.keyword_map.values() if a == aspect)
        print(f"    - {aspect.value}: {count} terms")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print(" KeywordExtractor Examples - Hybrid Keyword Extraction")
    print("=" * 80)

    try:
        example_1_dictionary_matching()
        example_2_aspect_mapping()
        example_3_hybrid_logic()
        example_4_real_world_reviews()
        example_5_performance_benchmark()

        print("\n" + "=" * 80)
        print(" All examples completed successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
