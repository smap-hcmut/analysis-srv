"""Example usage of TextPreprocessor."""

import sys
import os
from pprint import pprint

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.analytics.preprocessing import TextPreprocessor


def main():
    # Initialize preprocessor
    preprocessor = TextPreprocessor()

    # Example 1: Full post with transcription and comments
    print("\n--- Example 1: Full Post ---")
    input_data = {
        "content": {
            "text": "Amazing product! 🔥 #musthave #review",
            "transcription": "Today I am reviewing this amazing product. It has great features.",
        },
        "comments": [
            {"text": "Where can I buy?", "likes": 20},
            {"text": "Price?", "likes": 5},
            {"text": "Love it!", "likes": 50},
        ],
    }

    result = preprocessor.preprocess(input_data)
    print("Clean Text:", result.clean_text)
    print("Stats:")
    pprint(result.stats)
    print("Source Breakdown:")
    pprint(result.source_breakdown)

    # Example 2: Vietnamese content
    print("\n--- Example 2: Vietnamese Content ---")
    vn_input = {
        "content": {"text": "Xe chạy rất êm. Giá hợp lý. #VinFast #VF5", "transcription": None},
        "comments": [{"text": "Quá đẹp", "likes": 100}],
    }

    result_vn = preprocessor.preprocess(vn_input)
    print("Clean Text:", result_vn.clean_text)

    # Example 3: Spam/Noise
    print("\n--- Example 3: Spam Detection ---")
    spam_input = {
        "content": {"text": "#follow #like #share", "transcription": None},
        "comments": [],
    }

    result_spam = preprocessor.preprocess(spam_input)
    print("Hashtag Ratio:", result_spam.stats["hashtag_ratio"])
    print("Is Too Short:", result_spam.stats["is_too_short"])


if __name__ == "__main__":
    main()
