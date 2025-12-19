"""Example script for SentimentAnalyzer (ABSA).
Run with:
    uv run python examples/sentiment_example.py
"""

from pathlib import Path
from infrastructure.ai.phobert_onnx import PhoBERTONNX
from services.analytics.sentiment import SentimentAnalyzer


def main() -> None:
    # 1. Check if the model exists
    model_path = Path("infrastructure/phobert/models/model_quantized.onnx")
    if not model_path.exists():
        print(f"⚠️  PhoBERT model not found at {model_path}.")
        return

    # 2. Initialize Model
    print("⏳ Loading Model...")
    phobert = PhoBERTONNX()
    analyzer = SentimentAnalyzer(phobert)
    print("✅ Model Loaded!\n")

    # --- PHẦN 1: TEST ISOLATION (IMPORTANT) ---
    print("=" * 40)
    print("🧪 TEST 1: ISOLATION TEST (Kiểm tra não bộ Model)")
    print("=" * 40)

    test_phrases = [
        "Xe thiết kế rất đẹp",  # Expected: 5 stars (Positive)
        "giá quá cao",  # Expected: 1 star (Negative)
        "pin thì hơi yếu",  # Expected: 2 or 3 stars
    ]

    for phrase in test_phrases:
        # Direct call to the model (bypassing analyzer logic)
        raw_result = phobert.predict(phrase)
        print(f"Input: '{phrase}'")
        # Some models may not return 'label' in the result; handle gracefully
        rating = raw_result.get("rating", "?")
        label = raw_result.get("label", "N/A")
        confidence = raw_result.get("confidence", None)
        if confidence is not None:
            print(f" -> Rating: {rating} ⭐ | Label: {label} (Conf: {confidence:.4f})")
        else:
            print(f" -> Rating: {rating} ⭐ | Label: {label} (Conf: N/A)")
        print("-" * 20)

    # --- PHẦN 2: TEST FULL CONTEXT (Full system logic) ---
    print("\n" + "=" * 40)
    print("🧪 TEST 2: FULL SENTENCE (Kiểm tra Logic Analyzer)")
    print("=" * 40)

    text = "Xe thiết kế rất đẹp nhưng giá quá cao, pin thì hơi yếu."
    keywords = [
        {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")},
        {"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")},
        {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.find("pin")},
    ]

    result = analyzer.analyze(text, keywords)

    print(f'Full Text: "{text}"\n')
    overall_res = result.get("overall", {})
    overall_label = overall_res.get("label", "N/A")
    overall_rating = overall_res.get("rating", "N/A")
    print(f"Overall Sentiment: {overall_label} ({overall_rating}⭐)")
    print("\nAspect Breakdown:")

    for aspect, data in result.get("aspects", {}).items():
        aspect_label = data.get("label", "N/A")
        aspect_rating = data.get("rating", "N/A")
        aspect_conf = data.get("confidence", None)
        if aspect_conf is not None:
            print(f"- {aspect:<12}: {aspect_label} ({aspect_rating}⭐) | Conf: {aspect_conf:.4f}")
        else:
            print(f"- {aspect:<12}: {aspect_label} ({aspect_rating}⭐) | Conf: N/A")
        # If sentence splitting is incorrect, these confidence numbers will be identical


if __name__ == "__main__":
    main()
