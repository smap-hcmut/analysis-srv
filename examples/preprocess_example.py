"""Example usage of TextPreprocessor with multiple test cases."""

import sys
import os
import unicodedata
from pprint import pprint

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.analytics.preprocessing import TextPreprocessor


def run_test(name, input_data):
    """Run test using preprocess() method (returns PreprocessingResult object)."""
    preprocessor = TextPreprocessor()
    print(f"\n--- TEST CASE: {name} ---")
    print(f"Input Caption: {input_data.get('content', {}).get('text', '')[:50]}...")

    result = preprocessor.preprocess(input_data)

    print(f"Clean Text: [{result.clean_text}]")
    print("Metadata:")
    pprint(result.stats)
    print("Source Breakdown:")
    pprint(result.source_breakdown)
    return result


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

    # CASE 4: TEENCODE & VIẾT TẮT (Thử thách khả năng chuẩn hóa)
    # Kỳ vọng: Các từ 'ko', 'dc', 'vkl' nên được xử lý hoặc giữ nguyên có chủ đích
    case_teencode = {
        "content": {
            "text": "Xe chạy ngon vkl ae ơi :))) ko uổng tiền mua. sạc nhanh vãi chưởng.",
            "transcription": "hôm nay test con xe này thấy ổn áp phết, ko bị lag màn hình",
        },
        "comments": [],
    }

    # CASE 5: SPAM TINH VI (Spam dài, ít hashtag, nhưng chứa pattern rác)
    # Kỳ vọng: Preprocessor có phát hiện ra dấu hiệu bất thường không?
    case_spam_seo = {
        "content": {
            "text": "Hỗ trợ vay vốn lãi suất thấp. Giải ngân trong ngày. Liên hệ Zalo 0912345678 #vayvon #nhanhgon",
            "transcription": None,
        },
        "comments": [{"text": "Ib em nhé", "likes": 0}, {"text": "Uy tín", "likes": 0}],
    }

    # CASE 6: LỖI FONT UNICODE (Dựng sẵn vs Tổ hợp)
    # Chữ "Hòa" có 2 cách viết trong Unicode. PhoBERT chỉ hiểu 1 loại.
    # Kỳ vọng: Phải đưa về NFC chuẩn.
    text_nfd = unicodedata.normalize("NFD", "Xe VinFast Hòa Bình")  # Tạo text lỗi font
    case_encoding = {
        "content": {"text": text_nfd, "transcription": "Chạy rất êm ái"},
        "comments": [],
    }

    # CASE 7: NGỮ CẢNH RỜI RẠC (Caption ngắn, Video dài)
    # Kỳ vọng: Transcript phải được ưu tiên và nối câu hợp lý
    case_context = {
        "content": {
            "text": "Xem đi nè 👇👇",
            "transcription": "Đây là lỗi nghiêm trọng nhất của xe. Khi đang đi tốc độ cao thì bị mất lái.",
        },
        "comments": [{"text": "Sợ quá", "likes": 100}, {"text": "Hãng nói sao?", "likes": 50}],
    }

    # CASE 8: "RÁC" EMOJI & SPECIAL CHARS (Thử thách Regex)
    case_dirty = {
        "content": {
            "text": "🎀 𝐻𝑜𝑡 𝑇𝑟𝑒𝑛𝑑 🎀 𝑋𝑒 𝑉𝑖𝑛𝐹𝑎𝑠𝑡 🎀 𝐺𝑖𝑎́ 𝑅𝑒̉ 🎀",  # Font chữ kiểu teen
            "transcription": None,
        },
        "comments": [],
    }

    # --- EXECUTE ADVANCED TEST CASES ---
    run_test("4. Teencode & Slang", case_teencode)
    run_test("5. Hidden Spam", case_spam_seo)
    run_test("6. Unicode Encoding", case_encoding)
    run_test("7. Context Fusion", case_context)
    run_test("8. Special Fonts/Emoji", case_dirty)


if __name__ == "__main__":
    main()
