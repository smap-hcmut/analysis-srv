"""Example script for SentimentAnalyzer (ABSA).

Run with:
    uv run python examples/sentiment_example.py
"""

from pathlib import Path

from infrastructure.ai.phobert_onnx import PhoBERTONNX
from services.analytics.sentiment import SentimentAnalyzer


def main() -> None:
    # Ensure model exists
    model_path = Path("infrastructure/phobert/models/model_quantized.onnx")
    if not model_path.exists():
        print(
            "⚠️  PhoBERT model not found at "
            f"{model_path}.\n"
            "    Run 'make download-phobert' before running this example."
        )
        return

    phobert = PhoBERTONNX()
    analyzer = SentimentAnalyzer(phobert)

    text = "Xe thiết kế rất đẹp nhưng giá quá cao, pin thì hơi yếu."
    keywords = [
        {"keyword": "thiết kế", "aspect": "DESIGN", "position": text.find("thiết kế")},
        {"keyword": "giá", "aspect": "PRICE", "position": text.find("giá")},
        {"keyword": "pin", "aspect": "PERFORMANCE", "position": text.find("pin")},
    ]

    result = analyzer.analyze(text, keywords)

    print("Input text:")
    print(text)
    print("\nOverall sentiment:")
    print(result["overall"])
    print("\nAspect sentiments:")
    for aspect, data in result["aspects"].items():
        print(f"- {aspect}: {data}")


if __name__ == "__main__":
    main()
